from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_plist_has_run_command_and_schedule():
    t = (ROOT / "scheduler" / "com.balakumar.memory-gardener.plist").read_text()
    assert "-m" in t and "gardener" in t and "run" in t
    assert "StartCalendarInterval" in t or "StartInterval" in t
    assert "__PYTHON__" in t and "__REPO__" in t

def test_systemd_units_present():
    svc = (ROOT / "scheduler" / "memory-gardener.service").read_text()
    tmr = (ROOT / "scheduler" / "memory-gardener.timer").read_text()
    assert "ExecStart" in svc and "gardener" in svc and "run" in svc
    assert "[Timer]" in tmr and "OnCalendar" in tmr

def test_install_script_executable_and_mentions_home_pointer():
    s = (ROOT / "install.sh").read_text()
    assert "autoMemoryDirectory" in s and "~/.claude/memory/home" in s
    assert "migrate" in s

def test_install_prefers_system_python_and_guards_systemd():
    s = (ROOT / "install.sh").read_text()
    assert "/usr/bin/python3" in s            # prefers a stable system interpreter
    assert "command -v systemctl" in s        # guards the systemd branch
    assert "virtualenv" in s.lower()          # warns about venv interpreters
