from __future__ import annotations

import os
import subprocess
from pathlib import Path


def build_command(prompt_path, mem_dir, repo, digest_dir, model, tools, claude_bin):
    prompt_text = Path(prompt_path).read_text()
    prompt_text = prompt_text.format(mem_dir=mem_dir, repo=repo, digest_dir=digest_dir)
    return [
        claude_bin, "-p", prompt_text,
        "--model", model,
        "--tools", tools,
        "--permission-mode", "bypassPermissions",
        "--add-dir", str(mem_dir),
        "--add-dir", str(repo),
    ]


def build_env(base_env: dict) -> dict:
    env = dict(base_env)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def run_agent(prompt_path, mem_dir, repo, digest_dir, cfg, runner=subprocess.run):
    from .config import MODEL, TOOLS, CLAUDE_BIN
    cmd = build_command(prompt_path, mem_dir, repo, digest_dir, MODEL, TOOLS, CLAUDE_BIN)
    Path(mem_dir).mkdir(parents=True, exist_ok=True)
    proc = runner(cmd, cwd=str(cfg["GARDENER_DIR"]), env=build_env(os.environ),
                  capture_output=True, text=True)
    return proc.returncode
