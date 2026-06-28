from gardener.watermark import Watermark

def test_needs_unseen(tmp_path):
    wm = Watermark(tmp_path / "state.json")
    assert wm.needs("s1", 100.0) is True

def test_advance_then_not_needed(tmp_path):
    wm = Watermark(tmp_path / "state.json")
    wm.advance("s1", 100.0)
    assert wm.needs("s1", 100.0) is False
    assert wm.needs("s1", 150.0) is True  # newer mtime → reprocess

def test_persist_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    wm = Watermark(p); wm.advance("s1", 100.0); wm.save()
    wm2 = Watermark(p)
    assert wm2.needs("s1", 100.0) is False

def test_corrupt_file_resets(tmp_path):
    p = tmp_path / "state.json"; p.write_text("{not json")
    wm = Watermark(p)
    assert wm.needs("s1", 1.0) is True  # treated as empty

def test_non_dict_json_resets(tmp_path):
    for bad in ("[]", "42", "null", "\"foo\""):
        p = tmp_path / "state.json"
        p.write_text(bad)
        wm = Watermark(p)
        assert wm.needs("s1", 1.0) is True   # non-dict state treated as empty, no crash
