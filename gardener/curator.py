from __future__ import annotations

# gardener/curator.py — stage 2: the ONLY writer for ~/.claude/CLAUDE.md and
# ~/.claude/skills/. One invocation per run, after all per-project agents, so
# global decisions are made from cross-project evidence (the candidates queue)
# by a single writer — never by N project agents with keyhole views.
import os
import subprocess
import time
from pathlib import Path

from .agent import AGENT_TIMEOUT, build_env, resolve_config


def pending_candidates(path) -> int:
    """Count queued observation lines; 0 for a missing/unreadable queue."""
    try:
        text = Path(path).read_text()
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("- "))


def build_curator_command(prompt_path, cfg, model, tools, claude_bin,
                          mcp_config=None, extra_args=None, today=""):
    prompt_text = Path(prompt_path).read_text()
    prompt_text = prompt_text.format(
        claude_dir=cfg["CLAUDE_DIR"], claude_md=cfg["CLAUDE_DIR"] / "CLAUDE.md",
        skills_dir=cfg["SKILLS_DIR"], candidates_file=cfg["CANDIDATES_FILE"],
        memory_root=cfg["MEMORY_ROOT"], today=today)
    cmd = [claude_bin, "-p", prompt_text, "--model", model]
    if mcp_config:
        cmd += ["--strict-mcp-config", "--mcp-config", str(mcp_config)]
    cmd += ["--tools", tools, "--permission-mode", "bypassPermissions"]
    cmd += list(extra_args or [])
    cmd += ["--add-dir", str(cfg["CLAUDE_DIR"]), "--add-dir", str(cfg["MEMORY_ROOT"])]
    return cmd


def run_curator(prompt_path, cfg, runner=subprocess.run):
    c = resolve_config(os.environ)
    # The curator writes under ~/.claude with bypassPermissions; Bash would let
    # it escape the Edit/Write deny backstop and the kit repo's revertible
    # surface (e.g. shell-writing ~/.claude/hooks). It only edits text files,
    # so strip Bash from its toolset. Any other configured tool (incl. MCP
    # read tools) is preserved.
    curator_tools = ",".join(t for t in c["tools"].split(",") if t.strip() != "Bash")
    cmd = build_curator_command(prompt_path, cfg, c["curator_model"], curator_tools,
                                c["claude_bin"], mcp_config=c["mcp_config"],
                                extra_args=c["extra_args"],
                                today=time.strftime("%Y-%m-%d"))
    # Same no-capture rule as run_agent: pipes inherited by MCP-daemon
    # grandchildren outlive the agent and deadlock a read-to-EOF. DEVNULL only.
    try:
        proc = runner(cmd, cwd=str(cfg["GARDENER_DIR"]), env=build_env(os.environ),
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, timeout=AGENT_TIMEOUT)
        return proc.returncode
    except subprocess.TimeoutExpired:
        return 124
