import json
from pathlib import Path
from gardener.config import config_for
from gardener import migrate

def _seed_native_memory(cfg, key, cwd, fname, body):
    keydir = cfg["PROJECTS_DIR"] / key
    (keydir / "memory").mkdir(parents=True, exist_ok=True)
    (keydir / "memory" / fname).write_text(body)
    (keydir / "sess.jsonl").write_text(json.dumps(
        {"type": "user", "cwd": cwd, "message": {"role": "user", "content": "x"}}) + "\n")

def test_discover(tmp_path):
    cfg = config_for(tmp_path)
    _seed_native_memory(cfg, "-Users-x-workspace-factors", "/Users/x/workspace/factors",
                        "a.md", "---\nname: A\ndescription: d\n---\nbody")
    found = migrate.discover(cfg["PROJECTS_DIR"], cfg["HOME"])
    assert len(found) == 1
    name, old, new = found[0]
    assert name == "factors"
    assert new == cfg["MEMORY_ROOT"] / "factors"

def test_migrate_copies_and_backs_up(tmp_path):
    cfg = config_for(tmp_path)
    _seed_native_memory(cfg, "-k", "/Users/x/workspace/factors",
                        "a.md", "---\nname: A\ndescription: d\n---\nbody")
    out = migrate.migrate(cfg, now_date="2026-06-28")
    assert out["migrated"] == 1
    assert (cfg["MEMORY_ROOT"] / "factors" / "a.md").read_text().startswith("---")
    assert (cfg["MEMORY_ROOT"] / "factors" / "MEMORY.md").exists()
    assert (cfg["PROJECTS_DIR"] / "-k" / "memory.pre-migration.bak").is_dir()
    assert (cfg["MEMORY_ROOT"] / ".git").is_dir()  # committed baseline
