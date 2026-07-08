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


# ~/.claude is a busy directory (transcripts, plugins, caches, the nested
# memory repo). The kit repo tracks ONLY the curated surface: `/*` ignores
# every top-level entry; negations re-include exactly CLAUDE.md + skills/.
KIT_GITIGNORE = "/*\n!/.gitignore\n!/CLAUDE.md\n!/skills\n**/.DS_Store\n"


class KitGit(GitMemory):
    """Whitelist git repo over ~/.claude — the safety harness that makes
    autonomous curator edits to CLAUDE.md/skills revertible."""

    def _exclude_embedded_repos(self) -> None:
        # A skill vendored with its own .git would be captured as a gitlink by
        # `git add -A` (contents untracked, edits non-revertible). Keep such
        # skill dirs out of the kit entirely — append a /skills/<name>/ ignore
        # line (idempotent) and drop any already-tracked gitlink.
        skills = self.root / "skills"
        if not skills.is_dir():
            return
        gi = self.root / ".gitignore"
        existing = gi.read_text() if gi.exists() else ""
        add = []
        for dotgit in sorted(skills.glob("*/.git")):
            rel = "/skills/" + dotgit.parent.name + "/"
            if rel not in existing and rel not in add:
                add.append(rel)
                # if a prior run tracked it as a gitlink, untrack it
                self._git("rm", "-r", "--cached", "--quiet", "skills/" + dotgit.parent.name)
        if add:
            with open(gi, "a") as fh:
                for rel in add:
                    fh.write(rel + "\n")

    def bootstrap(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        gi = self.root / ".gitignore"
        if not gi.exists():  # never clobber a hand-written ignore file
            gi.write_text(KIT_GITIGNORE)
        self._exclude_embedded_repos()  # every run: keep vendored-git skills out
        if (self.root / ".git").is_dir():
            return
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Memory Gardener")
        self._git("config", "user.email", "gardener@localhost")
        self._git("add", ".gitignore")
        # plumbing-only init commit; the first "chore: snapshot manual edits"
        # commit (runner) captures the baseline CLAUDE.md/skills content.
        self._git("commit", "-m", "chore: init kit repo")
