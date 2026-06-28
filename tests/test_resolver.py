import json
from pathlib import Path
from gardener.resolver import slugify, logical_name, ensure_pointer

def test_slugify():
    assert slugify("workspace-factors") == "workspace-factors"
    assert slugify("Balakumar Dev!!") == "balakumar-dev"

def test_logical_name_home(tmp_path):
    assert logical_name(tmp_path, tmp_path) == "home"

def test_logical_name_project(tmp_path):
    repo = tmp_path / "workspace" / "factors"
    assert logical_name(repo, tmp_path) == "factors"

def test_ensure_pointer_creates_and_is_idempotent(tmp_path):
    home = tmp_path
    repo = tmp_path / "workspace" / "factors"
    mem = home / ".claude" / "memory" / "factors"
    changed1 = ensure_pointer(repo, mem, home=home)
    settings = repo / ".claude" / "settings.local.json"
    data = json.loads(settings.read_text())
    assert data["autoMemoryDirectory"] == "~/.claude/memory/factors"
    assert changed1 is True
    changed2 = ensure_pointer(repo, mem, home=home)
    assert changed2 is False  # already correct

def test_ensure_pointer_preserves_existing_keys(tmp_path):
    home = tmp_path
    repo = tmp_path / "r"
    settings = repo / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"keep": 1}))
    ensure_pointer(repo, home / ".claude/memory/r", home=home)
    data = json.loads(settings.read_text())
    assert data["keep"] == 1 and "autoMemoryDirectory" in data
