import subprocess
from pathlib import Path

import pytest

from gardener.gitmemory import GitMemory


def _has_git():
    return subprocess.run(["git", "--version"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not _has_git(), reason="git not installed")


def test_bootstrap_idempotent(tmp_path):
    gm = GitMemory(tmp_path); gm.bootstrap(); gm.bootstrap()
    assert (tmp_path / ".git").is_dir()
    assert "merge=union" in (tmp_path / ".gitattributes").read_text()


def test_bootstrap_writes_gitignore_excluding_cruft(tmp_path):
    gm = GitMemory(tmp_path); gm.bootstrap()
    gi = (tmp_path / ".gitignore").read_text()
    assert ".DS_Store" in gi and "__pycache__/" in gi and "*.pyc" in gi
    # ignored cruft must never be staged by commit_if_changed's `git add -A`
    (tmp_path / ".DS_Store").write_text("finder junk")
    assert gm.commit_if_changed("x") is False            # nothing real to commit
    status = gm._git("status", "--porcelain").stdout
    assert ".DS_Store" not in status                     # ignored → not staged/tracked


def test_commit_if_changed_scale_guard(tmp_path):
    gm = GitMemory(tmp_path); gm.bootstrap()
    assert gm.commit_if_changed("noop") is False        # nothing new
    (tmp_path / "factors").mkdir()
    (tmp_path / "factors" / "f.md").write_text("x")
    assert gm.commit_if_changed("add f") is True
    assert gm.commit_if_changed("again") is False        # clean again


def test_push_pull_via_local_bare_remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    a = tmp_path / "a"; a.mkdir(); gm = GitMemory(a); gm.bootstrap()
    gm._git("remote", "add", "origin", str(bare))
    (a / "x.md").write_text("hello"); gm.commit_if_changed("x")
    assert gm.push() is True
    b = tmp_path / "b"
    subprocess.run(["git", "clone", str(bare), str(b)], check=True, capture_output=True)
    assert (b / "x.md").read_text() == "hello"


def test_push_retries_via_pull_on_divergence(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    # A bootstraps, sets origin, lands the first commit.
    a = tmp_path / "a"; a.mkdir(); ga = GitMemory(a); ga.bootstrap()
    ga._git("remote", "add", "origin", str(bare))
    (a / "a.md").write_text("from A"); ga.commit_if_changed("a")
    assert ga.push() is True
    # B clones the bare AFTER A's push, then both A and B commit different files.
    b = tmp_path / "b"
    subprocess.run(["git", "clone", str(bare), str(b)], check=True, capture_output=True)
    gb = GitMemory(b)
    gb._git("config", "user.name", "Memory Gardener")
    gb._git("config", "user.email", "gardener@localhost")
    # A advances the remote so B is now stale (non-fast-forward on push).
    (a / "a2.md").write_text("from A again"); ga.commit_if_changed("a2"); assert ga.push() is True
    # B commits a DIFFERENT file → its first push is rejected → push() pulls (union-merge) and retries.
    (b / "b.md").write_text("from B"); gb.commit_if_changed("b")
    assert gb.push() is True
    # Both files must exist in the bare remote (verified via a fresh clone).
    c = tmp_path / "c"
    subprocess.run(["git", "clone", str(bare), str(c)], check=True, capture_output=True)
    assert (c / "a.md").read_text() == "from A"
    assert (c / "a2.md").read_text() == "from A again"
    assert (c / "b.md").read_text() == "from B"
