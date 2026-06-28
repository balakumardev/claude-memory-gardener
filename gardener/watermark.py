from __future__ import annotations

import json, os
from pathlib import Path

class Watermark:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if isinstance(data, dict):
                    self._data = data
            except (OSError, ValueError):
                self._data = {}

    def needs(self, session_id: str, mtime: float) -> bool:
        prev = self._data.get(session_id)
        return prev is None or mtime > prev

    def advance(self, session_id: str, mtime: float) -> None:
        self._data[session_id] = mtime

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        os.replace(tmp, self.path)
