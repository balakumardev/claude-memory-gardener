# tests/test_distiller.py
import json
from gardener.distiller import distill, strip_injected

def test_strip_injected():
    t = "keep <system-reminder>secret\nindex</system-reminder> end"
    assert "secret" not in strip_injected(t)
    assert "keep" in strip_injected(t) and "end" in strip_injected(t)

def _lines(*objs):
    return "\n".join(json.dumps(o) for o in objs) + "\n"

def test_distill_keeps_text_drops_noise():
    jsonl = _lines(
        {"type": "user", "cwd": "/r",
         "message": {"role": "user", "content": "Fix the build <system-reminder>NOISE</system-reminder>"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "secret reasoning", "signature": "x" * 2772},
            {"type": "text", "text": "Use make build"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "make build" * 500}},
        ]}},
        {"type": "attachment", "data": "x" * 9999},
        {"type": "file-history-snapshot", "blob": "x" * 9999},
        {"type": "system", "content": "session meta"},
    )
    out = distill(jsonl)
    assert "Fix the build" in out
    assert "Use make build" in out
    assert "[tool_use: Bash]" in out
    assert "NOISE" not in out             # injected block stripped
    assert "secret reasoning" not in out  # thinking dropped
    assert "session meta" not in out      # system line dropped
    assert "attachment" not in out and "file-history-snapshot" not in out
    # size: massive tool input and signature must not survive
    assert len(out) < 2000

def test_distill_truncates_long_message():
    jsonl = _lines({"type": "user", "message": {"role": "user", "content": "A" * 10000}})
    out = distill(jsonl, max_chars_per_msg=100)
    assert "[truncated]" in out and out.count("A") <= 100

def test_distill_skips_unparseable_lines():
    jsonl = "{bad json\n" + _lines({"type": "user", "message": {"role": "user", "content": "ok"}})
    assert "ok" in distill(jsonl)

def test_distill_user_content_list_routes_through_assistant_text():
    # real tool_result case: a user line whose content is a LIST of blocks
    jsonl = _lines({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": "RESULT_NOISE"},
        {"type": "text", "text": "keep me"},
    ]}})
    out = distill(jsonl)              # must not crash on the list branch
    assert "keep me" in out          # text block survives
    assert "RESULT_NOISE" not in out # tool_result dropped by _assistant_text
