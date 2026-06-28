from __future__ import annotations

import shutil
from pathlib import Path
from .gitmemory import GitMemory
from .memindex import regenerate_index
from .resolver import logical_name, slugify
from .scanner import first_cwd

def discover(projects_dir: Path, home: Path):
    projects_dir = Path(projects_dir); home = Path(home); out = []
    if not projects_dir.exists():
        return out
    for keydir in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
        mem = keydir / "memory"
        if not mem.is_dir() or not any(mem.glob("*.md")):
            continue
        cwd = None
        for t in keydir.glob("*.jsonl"):
            cwd = first_cwd(t)
            if cwd:
                break
        name = logical_name(Path(cwd), home) if cwd else slugify(keydir.name)
        out.append((name, mem, projects_dir.parent / "memory" / name))
    return out

def migrate(cfg: dict, now_date: str) -> dict:
    found = discover(cfg["PROJECTS_DIR"], cfg["HOME"])
    migrated = 0
    for name, old, new in found:
        if new.exists():
            continue
        new.mkdir(parents=True, exist_ok=True)
        for f in old.glob("*"):
            if f.is_file():
                shutil.copy2(f, new / f.name)
        regenerate_index(new)
        old.rename(old.parent / "memory.pre-migration.bak")
        migrated += 1
    gm = GitMemory(cfg["MEMORY_ROOT"]); gm.bootstrap()
    gm.commit_if_changed(f"migrate: relocate {migrated} native memory dirs ({now_date})")
    return {"migrated": migrated}
