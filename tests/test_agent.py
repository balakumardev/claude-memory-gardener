from pathlib import Path
from gardener import agent

def test_build_command_has_required_flags(tmp_path):
    (tmp_path / "p.md").write_text("stub prompt no braces")
    cmd = agent.build_command(tmp_path / "p.md", tmp_path / "mem", tmp_path / "repo",
                              tmp_path / "dig", model="haiku", tools="Read,Edit",
                              claude_bin="claude")
    assert "claude" in cmd[0]
    assert "-p" in cmd
    assert "--model" in cmd and "haiku" in cmd
    assert "--permission-mode" in cmd and "bypassPermissions" in cmd
    assert cmd.count("--add-dir") == 2

def test_build_env_disables_auto_memory():
    env = agent.build_env({"PATH": "/x"})
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert env["PATH"] == "/x"

def test_run_agent_uses_injected_runner(tmp_path):
    prompt = tmp_path / "p.md"; prompt.write_text("mem={mem_dir} repo={repo} dig={digest_dir}")
    captured = {}
    class R:
        returncode = 0
    def fake_runner(cmd, **kw):
        captured["cmd"] = cmd; captured["prompt"] = cmd[cmd.index("-p") + 1]; return R()
    from gardener.config import config_for
    cfg = config_for(tmp_path)
    rc = agent.run_agent(prompt, tmp_path / "mem", tmp_path / "repo", tmp_path / "dig",
                         cfg, runner=fake_runner)
    assert rc == 0
    assert str(tmp_path / "mem") in captured["prompt"]   # template substituted
    assert str(tmp_path / "repo") in captured["prompt"]
