from __future__ import annotations

# gardener/skillindex.py — deterministic inventory of global skills.
# Regenerated at the start of every run so per-project agents can detect
# "a skill should have triggered but didn't". Lives OUTSIDE both git repos
# (in GARDENER_DIR) so its churn never pollutes commits. No LLM involved.
from pathlib import Path

from .memindex import parse_frontmatter

MAX_DESC = 300
_HEADER = "# Global skills inventory (regenerated each run; name: description)\n\n"


def skill_line(skill_md: Path) -> str:
    fm = parse_frontmatter(skill_md.read_text())
    name = str(fm.get("name") or skill_md.parent.name).strip().strip('"').strip("'")
    desc = str(fm.get("description") or "").strip().strip('"').strip("'")
    if desc[:1] in (">", "|"):  # YAML block scalar indicator: body not line-parseable
        desc = ""
    if len(desc) > MAX_DESC:
        desc = desc[:MAX_DESC].rstrip() + "…"
    return f"- {name}: {desc}" if desc else f"- {name}"


def regenerate_skills_index(skills_dir: Path, out_file: Path) -> int:
    skills_dir, out_file = Path(skills_dir), Path(out_file)
    lines = []
    if skills_dir.is_dir():
        for sk in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                lines.append(skill_line(sk))
            except Exception:
                continue  # unreadable skill never blocks the run
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(_HEADER + "\n".join(lines) + ("\n" if lines else ""))
    return len(lines)
