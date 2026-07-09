import subprocess

from gardener import curator
from gardener.config import config_for


def _prompt(tmp_path):
    p = tmp_path / "curator.md"
    p.write_text("today={today} md={claude_md} skills={skills_dir} "
                 "queue={candidates_file} mem={memory_root} dir={claude_dir}")
    return p


def test_pending_candidates_counts_dated_entries(tmp_path):
    f = tmp_path / "candidates.md"
    assert curator.pending_candidates(f) == 0                    # missing file
    f.write_text(
        "# Global Observation Queue\n\n"
        "Append-only. A separate curator consumes this file.\n\n"
        "Format: `YYYY-MM-DD | <project> | NEW | <one-line summary> | evidence: <quote or what happened>`\n\n"
        "---\n"
        "2026-07-08 | p | NEW | a | evidence: e\n"
        "2026-07-08 | q | NEW | b | evidence: e\n"
    )
    assert curator.pending_candidates(f) == 2


def test_build_curator_command_substitutes_and_scopes(tmp_path):
    cfg = config_for(tmp_path)
    cmd = curator.build_curator_command(_prompt(tmp_path), cfg, model="haiku",
                                        tools="Read,Edit", claude_bin="claude",
                                        today="2026-07-08")
    prompt = cmd[cmd.index("-p") + 1]
    assert "2026-07-08" in prompt
    assert str(cfg["CLAUDE_DIR"] / "CLAUDE.md") in prompt
    assert str(cfg["SKILLS_DIR"]) in prompt and str(cfg["CANDIDATES_FILE"]) in prompt
    dirs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--add-dir"]
    assert dirs == [str(cfg["CLAUDE_DIR"]), str(cfg["MEMORY_ROOT"])]
    assert "--permission-mode" in cmd and "bypassPermissions" in cmd


def test_run_curator_uses_curator_model_and_devnull(tmp_path, monkeypatch):
    monkeypatch.setenv("GARDENER_MODEL", "base-model")
    monkeypatch.setenv("GARDENER_CURATOR_MODEL", "big-model")
    cfg = config_for(tmp_path)
    captured = {}
    class R:
        returncode = 0
    def fake_runner(cmd, **kw):
        captured["cmd"] = cmd; captured.update(kw); return R()
    rc = curator.run_curator(_prompt(tmp_path), cfg, runner=fake_runner)
    assert rc == 0
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == "big-model"
    assert captured["stdout"] == subprocess.DEVNULL
    assert captured["stderr"] == subprocess.DEVNULL
    assert "capture_output" not in captured
    assert captured["cwd"] == str(cfg["GARDENER_DIR"])
    assert isinstance(captured.get("timeout"), (int, float))


def test_run_curator_timeout_returns_124(tmp_path):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    rc = curator.run_curator(_prompt(tmp_path), config_for(tmp_path), runner=boom)
    assert rc == 124


def test_run_curator_strips_bash_from_tools(tmp_path, monkeypatch):
    # default TOOLS includes Bash; the curator must not receive it.
    cfg = config_for(tmp_path)
    captured = {}
    class R:
        returncode = 0
    def fake_runner(cmd, **kw):
        captured["cmd"] = cmd; return R()
    curator.run_curator(_prompt(tmp_path), cfg, runner=fake_runner)
    tools = captured["cmd"][captured["cmd"].index("--tools") + 1]
    assert "Bash" not in tools.split(",")
    assert "Read" in tools.split(",") and "Edit" in tools.split(",")
