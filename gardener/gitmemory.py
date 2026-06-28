from __future__ import annotations

# gardener/gitmemory.py
import subprocess
from pathlib import Path


class GitMemory:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True)

    def _has_origin(self) -> bool:
        return self._git("remote").stdout.find("origin") != -1

    def bootstrap(self) -> None:
        if (self.root / ".git").is_dir():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Memory Gardener")
        self._git("config", "user.email", "gardener@localhost")
        (self.root / ".gitattributes").write_text("*.md merge=union\n")
        (self.root / ".gitignore").write_text(".DS_Store\n__pycache__/\n*.pyc\n")
        self._git("add", ".gitattributes", ".gitignore")
        self._git("commit", "-m", "chore: init memory repo")

    def pull(self) -> bool:
        if not self._has_origin():
            return False
        if self._git("fetch", "origin").returncode != 0:
            return False
        return self._git("merge", "--no-edit", "origin/main").returncode == 0

    def commit_if_changed(self, message: str) -> bool:
        self._git("add", "-A")
        if self._git("diff", "--cached", "--quiet").returncode == 0:
            return False
        return self._git("commit", "-m", message).returncode == 0

    def push(self) -> bool:
        if not self._has_origin():
            return False
        if self._git("push", "origin", "main").returncode == 0:
            return True
        self.pull()
        return self._git("push", "origin", "main").returncode == 0
