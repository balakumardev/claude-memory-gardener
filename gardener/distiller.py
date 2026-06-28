from __future__ import annotations

# gardener/distiller.py
import json, re

_INJECTED = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<local-command-[^>]*>.*?</local-command-[^>]*>"
    r"|<command-[^>]*>.*?</command-[^>]*>",
    re.DOTALL,
)

def strip_injected(text: str) -> str:
    return _INJECTED.sub("", text)

def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n].rstrip() + " … [truncated]"

def _assistant_text(content) -> str:
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        bt = block.get("type")
        if bt == "text":
            parts.append(block.get("text", ""))
        elif bt == "tool_use":
            parts.append(f"[tool_use: {block.get('name', '?')}]")
        # thinking / tool_result and anything else: dropped
    return "\n".join(p for p in parts if p)

def distill(jsonl_text: str, max_chars_per_msg: int = 4000) -> str:
    out = []
    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        t = o.get("type")
        msg = o.get("message") or {}
        content = msg.get("content")
        if t == "user":
            text = content if isinstance(content, str) else _assistant_text(content or [])
            text = strip_injected(text)
            text = _truncate(text, max_chars_per_msg)
            if text:
                out.append(f"## User\n{text}")
        elif t == "assistant":
            text = _truncate(_assistant_text(content or []), max_chars_per_msg)
            if text:
                out.append(f"## Assistant\n{text}")
        # all other line types dropped
    return "\n\n".join(out) + ("\n" if out else "")
