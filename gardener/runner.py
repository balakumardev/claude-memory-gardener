from __future__ import annotations

import os, sys, time, traceback
from pathlib import Path
from . import agent as _agent
from . import curator as _curator
from .config import IDLE_SECONDS, STALE_LOCK_SECONDS
from .distiller import distill
from .gitmemory import GitMemory, KitGit
from .memindex import regenerate_index
from .resolver import logical_name, ensure_pointer
from .scanner import scan
from .skillindex import regenerate_skills_index
from .watermark import Watermark

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "gardener.md"
CURATOR_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "curator.md"


def _create_lock(lock_file: Path) -> bool:
    fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    return True


def acquire_lock(lock_file: Path, now: float | None = None,
                 stale_seconds: int = STALE_LOCK_SECONDS) -> bool:
    lock_file = Path(lock_file)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    if now is None:
        now = time.time()
    try:
        return _create_lock(lock_file)
    except FileExistsError:
        pass
    # Lock exists: reclaim it only if it is stale.
    try:
        if now - os.path.getmtime(str(lock_file)) <= stale_seconds:
            return False  # fresh lock held by a live run
        os.unlink(str(lock_file))  # stale → drop it
    except OSError:
        pass  # raced (vanished/changed); fall through to a single retry
    try:
        return _create_lock(lock_file)
    except FileExistsError:
        return False  # someone else grabbed it first


def release_lock(lock_file: Path) -> None:
    try:
        Path(lock_file).unlink()
    except FileNotFoundError:
        pass


def run_once(cfg: dict, now: float, agent_fn=_agent.run_agent, git_cls=GitMemory,
             curator_fn=_curator.run_curator, kit_cls=KitGit) -> dict:
    summary = {"processed": 0, "projects": 0, "committed": False, "curated": False}
    if not acquire_lock(cfg["LOCK_FILE"]):
        print("gardener: lock held, skipping run", file=sys.stderr)
        return summary
    try:
        gm = git_cls(cfg["MEMORY_ROOT"]); gm.bootstrap(); gm.pull()
        try:  # skills inventory is an input hint for the agents; never blocks a run
            regenerate_skills_index(cfg["SKILLS_DIR"], cfg["SKILLS_INDEX_FILE"])
        except Exception:
            cfg["LOG_DIR"].mkdir(parents=True, exist_ok=True)
            (cfg["LOG_DIR"] / "errors.log").open("a").write(
                f"skillindex: {traceback.format_exc()}\n")
        cfg["CANDIDATES_FILE"].parent.mkdir(parents=True, exist_ok=True)
        wm = Watermark(cfg["STATE_FILE"])
        transcripts = scan(cfg["PROJECTS_DIR"], wm, now, cfg["GARDENER_DIR"], IDLE_SECONDS)
        by_key = {}
        for t in transcripts:
            by_key.setdefault(t.key, []).append(t)
        committed_any = False
        for key, items in by_key.items():
            cwd = next((t.cwd for t in items if t.cwd), None)
            if not cwd:
                continue
            try:  # fail-open per project: one bad project never aborts the run (spec §12)
                repo = Path(cwd)
                name = logical_name(repo, cfg["HOME"])
                mem_dir = cfg["MEMORY_ROOT"] / name
                digest_dir = cfg["DIGEST_DIR"] / name
                digest_dir.mkdir(parents=True, exist_ok=True)
                for t in items:
                    (digest_dir / f"{t.session}.md").write_text(distill(t.path.read_text()))
                ensure_pointer(repo, mem_dir, home=cfg["HOME"])
                agent_fn(PROMPT, mem_dir, repo, digest_dir, cfg)
                regenerate_index(mem_dir)
                for t in items:  # advance only on success → failed project retries next run
                    wm.advance(t.session, t.mtime)
                wm.save()  # checkpoint per project → a kill resumes instead of redoing
                if gm.commit_if_changed(f"garden: {name} ({len(items)} sessions)"):
                    committed_any = True
                summary["processed"] += len(items)
                summary["projects"] += 1
                for f in digest_dir.glob("*.md"):
                    f.unlink()
            except Exception:
                cfg["LOG_DIR"].mkdir(parents=True, exist_ok=True)
                (cfg["LOG_DIR"] / "errors.log").open("a").write(
                    f"project {key}: {traceback.format_exc()}\n")
                print(f"gardener: skipped project {key} (see errors.log)", file=sys.stderr)
                continue
        # ---- stage 2: cross-project curator (single writer for ~/.claude) ----
        # Gate: sessions processed AND observations queued AND kill switch unset.
        if (summary["projects"] and not os.environ.get("GARDENER_NO_CURATE")
                and _curator.pending_candidates(cfg["CANDIDATES_FILE"])):
            try:  # fail-open: a bad curate never blocks memory work or the push
                kit = kit_cls(cfg["CLAUDE_DIR"]); kit.bootstrap()
                # capture the user's hand-edits first so the curate diff is isolated
                kit.commit_if_changed("chore: snapshot manual edits")
                curator_fn(CURATOR_PROMPT, cfg)
                if gm.commit_if_changed("curate: candidates queue"):
                    committed_any = True
                if kit.commit_if_changed("curate: skills + CLAUDE.md"):
                    summary["curated"] = True
                kit.push()
            except Exception:
                cfg["LOG_DIR"].mkdir(parents=True, exist_ok=True)
                (cfg["LOG_DIR"] / "errors.log").open("a").write(
                    f"curator: {traceback.format_exc()}\n")
                print("gardener: curator failed (see errors.log)", file=sys.stderr)
        # per-project commits already landed locally; push the batch once at the end
        summary["committed"] = committed_any
        if committed_any:
            gm.push()
        wm.save()
        return summary
    finally:
        release_lock(cfg["LOCK_FILE"])
