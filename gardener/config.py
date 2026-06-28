from __future__ import annotations

from pathlib import Path

IDLE_SECONDS = 1200
STALE_LOCK_SECONDS = 3600
MODEL = "haiku"
CLAUDE_BIN = "claude"
TOOLS = "Read,Edit,Write,Bash,Glob,Grep"


def config_for(home: Path) -> dict:
    claude = home / ".claude"
    gardener = claude / "gardener"
    return {
        "HOME": home,
        "PROJECTS_DIR": claude / "projects",
        "MEMORY_ROOT": claude / "memory",
        "GARDENER_DIR": gardener,
        "STATE_FILE": gardener / "state.json",
        "LOCK_FILE": gardener / "lock",
        "LOG_DIR": gardener / "log",
        "DIGEST_DIR": gardener / "digests",
    }


_d = config_for(Path.home())
HOME = _d["HOME"]; PROJECTS_DIR = _d["PROJECTS_DIR"]; MEMORY_ROOT = _d["MEMORY_ROOT"]
GARDENER_DIR = _d["GARDENER_DIR"]; STATE_FILE = _d["STATE_FILE"]; LOCK_FILE = _d["LOCK_FILE"]
LOG_DIR = _d["LOG_DIR"]; DIGEST_DIR = _d["DIGEST_DIR"]
