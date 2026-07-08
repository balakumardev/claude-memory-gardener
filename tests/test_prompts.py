# A stray literal { or } in a prompt file is a runtime KeyError/ValueError in
# .format() — these tests pin the exact kwarg sets the code passes.
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def test_gardener_prompt_formats_with_agent_kwargs():
    out = (PROMPTS / "gardener.md").read_text().format(
        mem_dir="/MEM", repo="/REPO", digest_dir="/DIG",
        candidates_file="/Q/candidates.md", skills_index="/G/skills-index.md")
    for token in ("/MEM", "/REPO", "/DIG", "/Q/candidates.md", "/G/skills-index.md"):
        assert token in out
    assert "{" not in out and "}" not in out


def test_curator_prompt_formats_with_curator_kwargs():
    out = (PROMPTS / "curator.md").read_text().format(
        claude_dir="/H/.claude", claude_md="/H/.claude/CLAUDE.md",
        skills_dir="/H/.claude/skills", candidates_file="/Q/candidates.md",
        memory_root="/H/.claude/memory", today="2026-07-08")
    for token in ("/H/.claude/CLAUDE.md", "/H/.claude/skills",
                  "/Q/candidates.md", "2026-07-08"):
        assert token in out
    assert "{" not in out and "}" not in out
    # the write-scope hard limit and the secrets ban must be present
    assert "plugins" in out and "settings" in out
    assert "NEVER write secret values" in out
