from __future__ import annotations

import json
import re
from pathlib import Path


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def logical_name(cwd: Path, home: Path) -> str:
    cwd = Path(cwd)
    home = Path(home)
    if cwd == home:
        return "home"
    return slugify(cwd.name)


def _mem_string(mem_dir: Path, home: Path) -> str:
    mem_dir = Path(mem_dir)
    home = Path(home)
    try:
        return "~/" + str(mem_dir.relative_to(home))
    except ValueError:
        return str(mem_dir)


def ensure_pointer(repo: Path, mem_dir: Path, home: Path | None = None) -> bool:
    home = Path(home) if home else Path.home()
    settings = Path(repo) / ".claude" / "settings.local.json"
    want = _mem_string(mem_dir, home)
    data = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text())
        except json.JSONDecodeError:
            data = {}
    if data.get("autoMemoryDirectory") == want:
        return False
    data["autoMemoryDirectory"] = want
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2) + "\n")
    return True
