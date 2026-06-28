from pathlib import Path
from gardener.config import config_for
from gardener import status

def test_status_counts(tmp_path):
    cfg = config_for(tmp_path)
    info = status.collect(cfg, now=0.0)
    assert "memory_root" in info and "pending" in info and "watermark_entries" in info
    assert info["pending"] == 0
