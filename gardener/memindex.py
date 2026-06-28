from __future__ import annotations

# gardener/memindex.py
from pathlib import Path

def parse_frontmatter(md: str) -> dict:
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end == -1:
        return {}
    block = md[3:end].strip("\n")
    fm, cur = {}, None
    for line in block.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":") and ":" == line.strip()[-1:]:
            cur = line.strip()[:-1]; fm[cur] = {}; continue
        if line.startswith(" ") and cur and ":" in line:
            k, _, v = line.strip().partition(":")
            fm[cur][k.strip()] = v.strip(); continue
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip(); cur = None
    return fm

def regenerate_index(mem_dir: Path) -> str:
    mem_dir = Path(mem_dir)
    lines = ["# Memory Index", ""]
    for f in sorted(mem_dir.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        fm = parse_frontmatter(f.read_text())
        title = fm.get("name") or f.stem
        desc = fm.get("description") or ""
        lines.append(f"- [{title}]({f.name}) — {desc}".rstrip(" —"))
    content = "\n".join(lines) + "\n"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "MEMORY.md").write_text(content)
    return content
