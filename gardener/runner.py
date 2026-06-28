from __future__ import annotations

import os, sys, time, traceback
from pathlib import Path
from . import agent as _agent
from .config import IDLE_SECONDS, STALE_LOCK_SECONDS
from .distiller import distill
from .gitmemory import GitMemory
from .memindex import regenerate_index
from .resolver import logical_name, ensure_pointer
from .scanner import scan
from .watermark import Watermark

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "gardener.md"


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


def run_once(cfg: dict, now: float, agent_fn=_agent.run_agent, git_cls=GitMemory) -> dict:
    summary = {"processed": 0, "projects": 0, "committed": False}
    if not acquire_lock(cfg["LOCK_FILE"]):
        print("gardener: lock held, skipping run", file=sys.stderr)
        return summary
    try:
        gm = git_cls(cfg["MEMORY_ROOT"]); gm.bootstrap(); gm.pull()
        wm = Watermark(cfg["STATE_FILE"])
        transcripts = scan(cfg["PROJECTS_DIR"], wm, now, cfg["GARDENER_DIR"], IDLE_SECONDS)
        by_key = {}
        for t in transcripts:
            by_key.setdefault(t.key, []).append(t)
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
        summary["committed"] = gm.commit_if_changed(
            f"garden: {summary['processed']} sessions across {summary['projects']} projects")
        if summary["committed"]:
            gm.push()
        wm.save()
        return summary
    finally:
        release_lock(cfg["LOCK_FILE"])
