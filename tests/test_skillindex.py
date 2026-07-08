from gardener.skillindex import regenerate_skills_index, MAX_DESC


def _mk_skill(root, slug, content):
    d = root / slug
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(content)


def test_index_lists_name_and_description_sorted(tmp_path):
    skills = tmp_path / "skills"
    _mk_skill(skills, "beta", '---\nname: beta\ndescription: "second thing"\n---\nbody\n')
    _mk_skill(skills, "alpha", "---\nname: alpha\ndescription: first thing\n---\nbody\n")
    out = tmp_path / "idx.md"
    n = regenerate_skills_index(skills, out)
    text = out.read_text()
    assert n == 2
    # sorted by directory, quotes stripped from the description
    assert text.index("- alpha: first thing") < text.index("- beta: second thing")


def test_index_falls_back_to_dir_name_and_truncates(tmp_path):
    skills = tmp_path / "skills"
    _mk_skill(skills, "noname", "---\ndescription: " + "x" * 400 + "\n---\n")
    out = tmp_path / "idx.md"
    regenerate_skills_index(skills, out)
    line = [l for l in out.read_text().splitlines() if l.startswith("- ")][0]
    assert line.startswith("- noname: ")
    assert line.endswith("…") and len(line) < MAX_DESC + 20


def test_index_handles_block_scalar_and_missing_dir(tmp_path):
    skills = tmp_path / "skills"
    # YAML block scalar (description: >) — line parser can't fold it; degrade to name-only
    _mk_skill(skills, "folded", "---\nname: folded\ndescription: >\n  long folded text\n---\n")
    out = tmp_path / "idx.md"
    regenerate_skills_index(skills, out)
    text = out.read_text()
    assert "- folded\n" in text        # degraded to name-only, no ": >" leaked
    assert ": >" not in text
    # missing skills dir → header-only file, count 0
    out2 = tmp_path / "idx2.md"
    assert regenerate_skills_index(tmp_path / "absent", out2) == 0
    assert out2.read_text().startswith("#")
