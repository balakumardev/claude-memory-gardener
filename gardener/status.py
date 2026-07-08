from __future__ import annotations

from .config import IDLE_SECONDS
from .curator import pending_candidates
from .scanner import scan
from .watermark import Watermark


def collect(cfg: dict, now: float) -> dict:
    """Read-only diagnostics: report what a run WOULD process, writing nothing.

    Loads the watermark (read-only) and scans the projects dir to count the
    transcripts a run would pick up right now. Does not write the watermark,
    create the memory repo, or invoke the agent.
    """
    wm = Watermark(cfg["STATE_FILE"])
    pending = scan(cfg["PROJECTS_DIR"], wm, now, cfg["GARDENER_DIR"], IDLE_SECONDS)
    return {
        "memory_root": str(cfg["MEMORY_ROOT"]),
        "memory_exists": (cfg["MEMORY_ROOT"] / ".git").is_dir(),
        "watermark_entries": len(wm._data),
        "pending": len(pending),
        "candidates_pending": pending_candidates(cfg["CANDIDATES_FILE"]),
    }
