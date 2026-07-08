from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


def build_command(prompt_path, mem_dir, repo, digest_dir, model, tools, claude_bin,
                  mcp_config=None, extra_args=None,
                  candidates_file=None, skills_index=None, curator_dir=None):
    prompt_text = Path(prompt_path).read_text()
    prompt_text = prompt_text.format(mem_dir=mem_dir, repo=repo, digest_dir=digest_dir,
                                     candidates_file=candidates_file or "",
                                     skills_index=skills_index or "")
    cmd = [claude_bin, "-p", prompt_text, "--model", model]
    if mcp_config:
        # Only the servers in mcp_config load; the user's global/project MCP
        # configs are ignored. Keeps a background run lean (no heavy/hanging
        # project MCP servers) while still allowing a chosen server.
        cmd += ["--strict-mcp-config", "--mcp-config", str(mcp_config)]
    cmd += ["--tools", tools, "--permission-mode", "bypassPermissions"]
    cmd += list(extra_args or [])
    cmd += ["--add-dir", str(mem_dir), "--add-dir", str(repo)]
    if curator_dir:  # queue dir sits outside mem_dir; agents append candidates there
        cmd += ["--add-dir", str(curator_dir)]
    return cmd


def build_env(base_env: dict) -> dict:
    env = dict(base_env)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def resolve_config(env: dict) -> dict:
    """Resolve the agent invocation from the environment. All overrides are
    optional; with none set, behaviour matches the built-in defaults.

      GARDENER_CLAUDE_BIN   path/name of the claude binary       (default: claude)
      GARDENER_MODEL        model passed to --model              (default: haiku)
      GARDENER_CURATOR_MODEL  model for the stage-2 curator; falls back to
                              GARDENER_MODEL, then the built-in default
      GARDENER_MCP_CONFIG   path to an MCP config; when set, runs with
                            --strict-mcp-config --mcp-config <path> so ONLY those
                            servers load                          (default: none)
      GARDENER_TOOLS_EXTRA  extra tool name(s) appended to --tools (e.g. an MCP
                            tool like mcp__code-index__search)
      GARDENER_EXTRA_ARGS   extra flags appended verbatim (shlex-split)

    Any ANTHROPIC_* / provider env in the process environment is passed through
    to the claude subprocess (see build_env), so custom model routing works
    without touching this code.
    """
    from .config import MODEL, TOOLS, CLAUDE_BIN
    tools = TOOLS
    extra_tools = (env.get("GARDENER_TOOLS_EXTRA") or "").strip().strip(",")
    if extra_tools:
        tools = tools + "," + extra_tools
    return {
        "claude_bin": env.get("GARDENER_CLAUDE_BIN") or CLAUDE_BIN,
        "model": env.get("GARDENER_MODEL") or MODEL,
        "curator_model": (env.get("GARDENER_CURATOR_MODEL")
                          or env.get("GARDENER_MODEL") or MODEL),
        "tools": tools,
        "mcp_config": env.get("GARDENER_MCP_CONFIG") or None,
        "extra_args": shlex.split(env.get("GARDENER_EXTRA_ARGS", "")),
    }


# Hard backstop on a single agent invocation (a wrapper may impose a tighter
# one). Bounds any hang so one project can never wedge the whole run.
AGENT_TIMEOUT = 2000


def run_agent(prompt_path, mem_dir, repo, digest_dir, cfg, runner=subprocess.run):
    c = resolve_config(os.environ)
    cmd = build_command(prompt_path, mem_dir, repo, digest_dir,
                        c["model"], c["tools"], c["claude_bin"],
                        mcp_config=c["mcp_config"], extra_args=c["extra_args"],
                        candidates_file=cfg.get("CANDIDATES_FILE"),
                        skills_index=cfg.get("SKILLS_INDEX_FILE"),
                        curator_dir=cfg.get("CURATOR_DIR"))
    Path(mem_dir).mkdir(parents=True, exist_ok=True)
    # Do NOT capture output. We only use the return code, and capturing creates
    # stdout/stderr pipes that long-lived MCP daemons spawned as the agent's
    # grandchildren inherit and hold open — so reading-to-EOF deadlocks forever
    # after the agent itself exits. DEVNULL avoids the pipe entirely; the agent
    # records its own transcript under ~/.claude/projects/<gardener>/ if needed.
    try:
        proc = runner(cmd, cwd=str(cfg["GARDENER_DIR"]), env=build_env(os.environ),
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, timeout=AGENT_TIMEOUT)
        return proc.returncode
    except subprocess.TimeoutExpired:
        return 124
