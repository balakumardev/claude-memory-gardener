import json, os, subprocess
from pathlib import Path
from gardener.config import config_for
from gardener import runner


def _write_transcript(proj_key_dir: Path, session: str, cwd: str, mtime: float, text: str):
    proj_key_dir.mkdir(parents=True, exist_ok=True)
    p = proj_key_dir / f"{session}.jsonl"
    p.write_text(json.dumps({"type": "user", "cwd": cwd,
                             "message": {"role": "user", "content": text}}) + "\n")
    os.utime(p, (mtime, mtime))


def test_lock(tmp_path):
    lf = tmp_path / "lock"
    assert runner.acquire_lock(lf) is True
    assert runner.acquire_lock(lf) is False
    runner.release_lock(lf)
    assert runner.acquire_lock(lf) is True


def test_lock_fresh_not_reclaimed(tmp_path):
    lf = tmp_path / "lock"
    assert runner.acquire_lock(lf) is True               # holds the lock
    # a just-created lock is fresh → a second acquirer must back off
    assert runner.acquire_lock(lf, now=os.path.getmtime(lf) + 10) is False


def test_lock_stale_reclaimed(tmp_path):
    lf = tmp_path / "lock"
    assert runner.acquire_lock(lf) is True
    before = os.path.getmtime(lf)
    # force staleness without sleeping: pretend "now" is far past the stale window
    assert runner.acquire_lock(lf, now=before + runner.STALE_LOCK_SECONDS + 1) is True
    assert lf.exists()                                   # lock was re-created
    # also works by aging the file's mtime directly
    old = before - runner.STALE_LOCK_SECONDS - 100
    os.utime(lf, (old, old))
    assert runner.acquire_lock(lf) is True


def test_run_once_end_to_end(tmp_path):
    home = tmp_path
    cfg = config_for(home)
    repo = home / "workspace" / "factors"; repo.mkdir(parents=True)
    key = "-Users-x-workspace-factors"
    _write_transcript(cfg["PROJECTS_DIR"] / key, "s1", str(repo), 1000.0, "use pnpm not npm")

    # fake agent: simulate the LLM writing one memory file into mem_dir
    def fake_agent(prompt_path, mem_dir, repo_, digest_dir, c, runner=None):
        Path(mem_dir).mkdir(parents=True, exist_ok=True)
        (Path(mem_dir) / "pkg-manager.md").write_text(
            "---\nname: Package manager\ndescription: use pnpm\n---\nUse pnpm, not npm.\n")
        return 0

    summary = runner.run_once(cfg, now=1000.0 + 5000, agent_fn=fake_agent)
    assert summary["processed"] == 1
    mem = cfg["MEMORY_ROOT"] / "factors"
    assert (mem / "pkg-manager.md").exists()
    assert "pkg-manager.md" in (mem / "MEMORY.md").read_text()       # index regenerated
    # pointer written into the repo
    sj = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert sj["autoMemoryDirectory"] == "~/.claude/memory/factors"
    # committed to the memory repo
    log = subprocess.run(["git", "-C", str(cfg["MEMORY_ROOT"]), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    assert "garden:" in log
    # watermark advanced → second run is a no-op
    summary2 = runner.run_once(cfg, now=1000.0 + 6000, agent_fn=fake_agent)
    assert summary2["processed"] == 0 and summary2["committed"] is False


def test_run_once_fail_open(tmp_path):
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")

    def boom(*a, **k):
        raise RuntimeError("agent exploded")

    summary = runner.run_once(cfg, now=1000.0 + 5000, agent_fn=boom)
    assert summary["processed"] == 0                 # project skipped, run did not crash
    assert (cfg["LOG_DIR"] / "errors.log").exists()  # error logged
    # watermark NOT advanced → the failed session is retried on the next run
    again = runner.run_once(cfg, now=1000.0 + 6000, agent_fn=boom)
    assert again["processed"] == 0
    from gardener.watermark import Watermark
    assert Watermark(cfg["STATE_FILE"]).needs("s1", 1000.0) is True


def _cand_line(project="factors"):
    return f"2026-07-08 | {project} | NEW | uses pnpm everywhere | evidence: said so\n"


def test_run_once_curates_when_queue_nonempty(tmp_path, monkeypatch):
    monkeypatch.delenv("GARDENER_NO_CURATE", raising=False)
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")

    def fake_agent(prompt_path, mem_dir, repo_, digest_dir, c, runner=None):
        with open(c["CANDIDATES_FILE"], "a") as fh:   # runner pre-creates the dir
            fh.write(_cand_line())
        return 0

    def fake_curator(prompt_path, c, runner=None):
        # simulate: applies the line → clears queue + writes a global skill
        c["CANDIDATES_FILE"].write_text("")
        sk = c["SKILLS_DIR"] / "pnpm"; sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text("---\nname: pnpm\ndescription: use pnpm\n---\nrun pnpm\n")
        return 0

    summary = runner.run_once(cfg, now=6000.0, agent_fn=fake_agent, curator_fn=fake_curator)
    assert summary["curated"] is True
    # queue rewrite is committed to the memory repo
    log = subprocess.run(["git", "-C", str(cfg["MEMORY_ROOT"]), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    assert "curate: candidates queue" in log
    # curator's changes land in the kit repo, isolated in a curate commit
    klog = subprocess.run(["git", "-C", str(cfg["CLAUDE_DIR"]), "log", "--oneline"],
                          capture_output=True, text=True).stdout
    assert "curate: skills + CLAUDE.md" in klog and "chore: init kit repo" in klog


def test_run_once_skips_curator_when_queue_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("GARDENER_NO_CURATE", raising=False)
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")
    called = []
    summary = runner.run_once(cfg, now=6000.0,
                              agent_fn=lambda *a, **k: 0,
                              curator_fn=lambda *a, **k: called.append(1))
    assert called == [] and summary["curated"] is False
    assert not (cfg["CLAUDE_DIR"] / ".git").exists()   # kit repo not even created


def test_run_once_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("GARDENER_NO_CURATE", "1")
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")

    def fake_agent(prompt_path, mem_dir, repo_, digest_dir, c, runner=None):
        c["CANDIDATES_FILE"].write_text(_cand_line())
        return 0

    called = []
    summary = runner.run_once(cfg, now=6000.0, agent_fn=fake_agent,
                              curator_fn=lambda *a, **k: called.append(1))
    assert called == [] and summary["curated"] is False


def test_run_once_curator_failure_is_fail_open(tmp_path, monkeypatch):
    monkeypatch.delenv("GARDENER_NO_CURATE", raising=False)
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")

    def fake_agent(prompt_path, mem_dir, repo_, digest_dir, c, runner=None):
        Path(mem_dir).mkdir(parents=True, exist_ok=True)
        (Path(mem_dir) / "f.md").write_text("---\nname: f\ndescription: d\n---\nx\n")
        c["CANDIDATES_FILE"].write_text(_cand_line())
        return 0

    def boom_curator(*a, **k):
        raise RuntimeError("curator exploded")

    summary = runner.run_once(cfg, now=6000.0, agent_fn=fake_agent, curator_fn=boom_curator)
    assert summary["processed"] == 1 and summary["committed"] is True   # memory intact
    assert summary["curated"] is False
    assert "curator:" in (cfg["LOG_DIR"] / "errors.log").read_text()


def test_run_once_kit_commit_order(tmp_path, monkeypatch):
    monkeypatch.delenv("GARDENER_NO_CURATE", raising=False)
    cfg = config_for(tmp_path)
    repo = tmp_path / "workspace" / "factors"; repo.mkdir(parents=True)
    _write_transcript(cfg["PROJECTS_DIR"] / "-k", "s1", str(repo), 1000.0, "x")
    events = []

    def fake_agent(prompt_path, mem_dir, repo_, digest_dir, c, runner=None):
        c["CANDIDATES_FILE"].write_text(_cand_line())
        return 0

    class FakeKit:
        def __init__(self, root):
            events.append(("init", Path(root)))
        def bootstrap(self):
            events.append(("bootstrap",))
        def commit_if_changed(self, msg):
            events.append(("commit", msg)); return True
        def push(self):
            events.append(("push",)); return True

    runner.run_once(cfg, now=6000.0, agent_fn=fake_agent,
                    curator_fn=lambda *a, **k: events.append(("curator",)),
                    kit_cls=FakeKit)
    assert [e[0] for e in events] == ["init", "bootstrap", "commit", "curator",
                                      "commit", "push"]
    assert events[0][1] == cfg["CLAUDE_DIR"]
    assert events[2] == ("commit", "chore: snapshot manual edits")
    assert events[4] == ("commit", "curate: skills + CLAUDE.md")
