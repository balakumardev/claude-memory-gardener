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


def test_resolve_config_defaults():
    from gardener.config import MODEL, TOOLS, CLAUDE_BIN
    c = agent.resolve_config({})  # no overrides
    assert c["model"] == MODEL and c["claude_bin"] == CLAUDE_BIN
    assert c["tools"] == TOOLS and c["mcp_config"] is None and c["extra_args"] == []


def test_resolve_config_env_overrides():
    c = agent.resolve_config({
        "GARDENER_CLAUDE_BIN": "/opt/claude",
        "GARDENER_MODEL": "vendor/custom-model",
        "GARDENER_MCP_CONFIG": "/cfg/mcp.json",
        "GARDENER_TOOLS_EXTRA": "mcp__code-index__search",
        "GARDENER_EXTRA_ARGS": "--max-turns 40 --foo bar",
    })
    assert c["claude_bin"] == "/opt/claude" and c["model"] == "vendor/custom-model"
    assert c["mcp_config"] == "/cfg/mcp.json"
    assert c["tools"].endswith(",mcp__code-index__search")
    assert c["extra_args"] == ["--max-turns", "40", "--foo", "bar"]


def test_build_command_with_mcp_config_and_extra(tmp_path):
    (tmp_path / "p.md").write_text("stub")
    cmd = agent.build_command(tmp_path / "p.md", tmp_path / "mem", tmp_path / "repo",
                              tmp_path / "dig", model="vendor/custom-model",
                              tools="Read,mcp__code-index__search",
                              claude_bin="claude", mcp_config="/cfg/mcp.json",
                              extra_args=["--max-turns", "40"])
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == "/cfg/mcp.json"
    assert "vendor/custom-model" in cmd and "--max-turns" in cmd
    assert "mcp__code-index__search" in cmd[cmd.index("--tools") + 1]


def test_build_command_no_mcp_by_default(tmp_path):
    (tmp_path / "p.md").write_text("stub")
    cmd = agent.build_command(tmp_path / "p.md", tmp_path / "mem", tmp_path / "repo",
                              tmp_path / "dig", model="haiku", tools="Read",
                              claude_bin="claude")
    assert "--strict-mcp-config" not in cmd and "--mcp-config" not in cmd


def test_run_agent_does_not_capture_output(tmp_path):
    # Capturing creates pipes that long-lived MCP-daemon grandchildren inherit
    # and hold open, deadlocking us after the agent exits. Must use DEVNULL + a
    # timeout instead.
    import subprocess
    prompt = tmp_path / "p.md"; prompt.write_text("x")
    captured = {}
    class R:
        returncode = 0
    def fake_runner(cmd, **kw):
        captured.update(kw); return R()
    from gardener.config import config_for
    agent.run_agent(prompt, tmp_path / "mem", tmp_path / "repo", tmp_path / "dig",
                    config_for(tmp_path), runner=fake_runner)
    assert "capture_output" not in captured
    assert captured.get("stdout") == subprocess.DEVNULL
    assert captured.get("stderr") == subprocess.DEVNULL
    assert isinstance(captured.get("timeout"), (int, float))


def test_run_agent_timeout_is_fail_open(tmp_path):
    import subprocess
    prompt = tmp_path / "p.md"; prompt.write_text("x")
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    from gardener.config import config_for
    rc = agent.run_agent(prompt, tmp_path / "mem", tmp_path / "repo", tmp_path / "dig",
                         config_for(tmp_path), runner=boom)
    assert rc == 124  # non-zero so the run continues to the next project
