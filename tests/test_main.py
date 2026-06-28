from __future__ import annotations

import gardener.runner
import gardener.status
import gardener.migrate
from gardener import __main__ as m


def test_help_and_unknown():
    assert m.main([]) == 0
    assert m.main(["help"]) == 0
    assert m.main(["bogus"]) == 2


def test_run_subcommand_executes(monkeypatch, capsys):
    # Regression: the status branch's local `import time` once shadowed the
    # module-level `time`, so the run branch's `time.time()` raised
    # UnboundLocalError — breaking every scheduled run. main(["run"]) must work.
    monkeypatch.setattr(gardener.runner, "run_once",
                        lambda cfg, now: {"processed": 0, "projects": 0, "committed": False})
    assert m.main(["run"]) == 0
    assert "garden:" in capsys.readouterr().out


def test_status_subcommand_executes(monkeypatch, capsys):
    monkeypatch.setattr(gardener.status, "collect",
                        lambda cfg, now: {"memory_root": "x", "memory_exists": False,
                                          "watermark_entries": 0, "pending": 0})
    assert m.main(["status"]) == 0
    assert "pending" in capsys.readouterr().out


def test_migrate_subcommand_executes(monkeypatch, capsys):
    monkeypatch.setattr(gardener.migrate, "migrate", lambda cfg, now_date: {"migrated": 0})
    assert m.main(["migrate"]) == 0
    assert "migrate:" in capsys.readouterr().out
