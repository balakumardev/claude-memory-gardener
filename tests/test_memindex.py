# tests/test_memindex.py
from gardener.memindex import parse_frontmatter, regenerate_index

def test_parse_frontmatter_flat_and_nested():
    md = "---\nname: foo-bar\ndescription: A thing\nmetadata:\n  type: project\n---\nbody"
    fm = parse_frontmatter(md)
    assert fm["name"] == "foo-bar"
    assert fm["description"] == "A thing"
    assert fm["metadata"]["type"] == "project"

def test_parse_frontmatter_absent():
    assert parse_frontmatter("no frontmatter here") == {}

def test_regenerate_index(tmp_path):
    (tmp_path / "b_fact.md").write_text("---\nname: B Fact\ndescription: second\n---\nx")
    (tmp_path / "a_fact.md").write_text("---\nname: A Fact\ndescription: first\n---\nx")
    (tmp_path / "MEMORY.md").write_text("stale")
    content = regenerate_index(tmp_path)
    # sorted by filename: a_fact before b_fact; MEMORY.md excluded from its own index
    assert content.index("a_fact.md") < content.index("b_fact.md")
    assert "MEMORY.md)" not in content
    assert "[A Fact](a_fact.md) — first" in content
    assert (tmp_path / "MEMORY.md").read_text() == content
