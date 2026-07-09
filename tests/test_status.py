from pathlib import Path
from gardener.config import config_for
from gardener import status

def test_status_counts(tmp_path):
    cfg = config_for(tmp_path)
    info = status.collect(cfg, now=0.0)
    assert "memory_root" in info and "pending" in info and "watermark_entries" in info
    assert info["pending"] == 0

def test_status_reports_pending_candidates(tmp_path):
    cfg = config_for(tmp_path)
    assert status.collect(cfg, now=0.0)["candidates_pending"] == 0
    cfg["CANDIDATES_FILE"].parent.mkdir(parents=True)
    cfg["CANDIDATES_FILE"].write_text("2026-07-08 | p | NEW | a | e\n")
    assert status.collect(cfg, now=0.0)["candidates_pending"] == 1
