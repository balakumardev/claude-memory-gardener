from pathlib import Path
from gardener.config import config_for, IDLE_SECONDS, MODEL


def test_config_for_derives_paths_from_home():
    cfg = config_for(Path("/tmp/fakehome"))
    assert cfg["PROJECTS_DIR"] == Path("/tmp/fakehome/.claude/projects")
    assert cfg["MEMORY_ROOT"] == Path("/tmp/fakehome/.claude/memory")
    assert cfg["GARDENER_DIR"] == Path("/tmp/fakehome/.claude/gardener")
    assert cfg["STATE_FILE"] == Path("/tmp/fakehome/.claude/gardener/state.json")


def test_scalars():
    assert IDLE_SECONDS == 1200
    assert MODEL == "haiku"


def test_config_for_curation_paths():
    cfg = config_for(Path("/tmp/fakehome"))
    assert cfg["CLAUDE_DIR"] == Path("/tmp/fakehome/.claude")
    assert cfg["SKILLS_DIR"] == Path("/tmp/fakehome/.claude/skills")
    assert cfg["CURATOR_DIR"] == Path("/tmp/fakehome/.claude/memory/_curator")
    assert cfg["CANDIDATES_FILE"] == Path(
        "/tmp/fakehome/.claude/memory/_curator/candidates.md")
    assert cfg["SKILLS_INDEX_FILE"] == Path(
        "/tmp/fakehome/.claude/gardener/skills-index.md")
