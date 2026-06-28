from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gardener.watermark import Watermark


@dataclass
class Transcript:
    key: str
    session: str
    path: Path
    mtime: float
    cwd: str | None


def first_cwd(path: Path) -> str | None:
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(o, dict) and o.get("cwd"):
                    return o["cwd"]
    except OSError:
        return None
    return None


def _under(child: str, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def scan(projects_dir: Path, wm: Watermark, now: float, gardener_dir: Path, idle: int = 1200) -> list[Transcript]:
    projects_dir = Path(projects_dir)
    out = []
    if not projects_dir.exists():
        return out
    for path in projects_dir.glob("*/*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        session = path.stem
        if not wm.needs(session, mtime):
            continue
        if now - mtime < idle:
            continue
        cwd = first_cwd(path)
        if cwd and _under(cwd, gardener_dir):
            continue
        out.append(Transcript(path.parent.name, session, path, mtime, cwd))
    out.sort(key=lambda t: t.mtime)
    return out
