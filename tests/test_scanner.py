import json, os
from pathlib import Path
from gardener.watermark import Watermark
from gardener.scanner import scan, first_cwd

def _write(p: Path, cwd: str, mtime: float):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"type": "user", "cwd": cwd,
                             "message": {"role": "user", "content": "hi"}}) + "\n")
    os.utime(p, (mtime, mtime))

def test_first_cwd(tmp_path):
    p = tmp_path / "x.jsonl"; _write(p, "/Users/bala/repo", 100.0)
    assert first_cwd(p) == "/Users/bala/repo"

def test_scan_picks_idle_unseen(tmp_path):
    proj = tmp_path / "projects"
    _write(proj / "-Users-bala-repo" / "s1.jsonl", "/Users/bala/repo", 1000.0)
    wm = Watermark(tmp_path / "state.json")
    out = scan(proj, wm, now=1000.0 + 2000, gardener_dir=tmp_path / "g")
    assert len(out) == 1 and out[0].session == "s1" and out[0].cwd == "/Users/bala/repo"

def test_scan_skips_live(tmp_path):
    proj = tmp_path / "projects"
    _write(proj / "-k" / "s1.jsonl", "/Users/bala/repo", 5000.0)
    wm = Watermark(tmp_path / "state.json")
    assert scan(proj, wm, now=5000.0 + 60, gardener_dir=tmp_path / "g") == []  # 60s < idle

def test_scan_skips_seen(tmp_path):
    proj = tmp_path / "projects"
    _write(proj / "-k" / "s1.jsonl", "/Users/bala/repo", 1000.0)
    wm = Watermark(tmp_path / "state.json"); wm.advance("s1", 1000.0)
    assert scan(proj, wm, now=999999.0, gardener_dir=tmp_path / "g") == []

def test_scan_excludes_gardener_cwd(tmp_path):
    proj = tmp_path / "projects"; g = tmp_path / "g"
    _write(proj / "-g" / "s1.jsonl", str(g / "sub"), 1000.0)
    wm = Watermark(tmp_path / "state.json")
    assert scan(proj, wm, now=999999.0, gardener_dir=g) == []
