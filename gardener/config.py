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
        "CLAUDE_DIR": claude,
        "SKILLS_DIR": claude / "skills",
        "CURATOR_DIR": claude / "memory" / "_curator",
        "CANDIDATES_FILE": claude / "memory" / "_curator" / "candidates.md",
        "SKILLS_INDEX_FILE": gardener / "skills-index.md",
    }


_d = config_for(Path.home())
HOME = _d["HOME"]; PROJECTS_DIR = _d["PROJECTS_DIR"]; MEMORY_ROOT = _d["MEMORY_ROOT"]
GARDENER_DIR = _d["GARDENER_DIR"]; STATE_FILE = _d["STATE_FILE"]; LOCK_FILE = _d["LOCK_FILE"]
LOG_DIR = _d["LOG_DIR"]; DIGEST_DIR = _d["DIGEST_DIR"]
CLAUDE_DIR = _d["CLAUDE_DIR"]; SKILLS_DIR = _d["SKILLS_DIR"]; CURATOR_DIR = _d["CURATOR_DIR"]
CANDIDATES_FILE = _d["CANDIDATES_FILE"]; SKILLS_INDEX_FILE = _d["SKILLS_INDEX_FILE"]
