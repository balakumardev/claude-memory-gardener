---
name: memory-gardener-setup
description: Set up (or update) the Memory Gardener on this machine — the offline agent that distills Claude Code session transcripts into git-backed native memory and curates skills + global CLAUDE.md. Use when the user asks to install/set up/deploy the memory gardener, add it to a new Mac or Linux box, configure its model routing, or wire up its scheduler. Triggers on "set up memory gardener", "install the gardener", "gardener on this mac", "run setup.sh".
---

# Memory Gardener — machine setup

Goal: get the gardener running as a scheduled background job on THIS machine, routed to a **cheap** model, isolated and safe.

## Steps

1. **Preflight.** Confirm from the repo root:
   - `command -v claude` (Claude Code installed) and `python3 --version` (>= 3.9).
   - `python3 -m pytest -q` passes (optional sanity).

2. **Run the turnkey installer** from the repo root:
   ```bash
   ./setup.sh
   ```
   It installs the shim, deny backstop, `run.sh` (with catch-up), runs the one-time `migrate`, and loads the scheduler (launchd/systemd). It never clobbers an existing `~/.claude/gardener/gardener.env`.

3. **Route to a cheap model (important).** Without this, batch gardening 3×/day uses the user's normal `claude` auth + default model (possibly expensive). Ask the user which cheap model/route they want, then edit `~/.claude/gardener/gardener.env` following [`setup/gardener.env.example`](../../../setup/gardener.env.example):
   - an Anthropic-compatible proxy (set `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` + `GARDENER_MODEL`), or
   - a local loopback router / CCR (set `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`, `GARDENER_STRIP_MODEL=1`, and `GARDENER_CCR_LABEL`/`GARDENER_CCR_PORT` so the shim pre-warms it).
   Never put real keys in the repo — only in the local `gardener.env`.

4. **home project pointer** (optional): add `"autoMemoryDirectory": "~/.claude/memory/home"` to `~/.claude/settings.json`.

5. **Cross-machine sync** (optional): add a **private** git remote to `~/.claude/memory` and push. **Skip on a work machine** to keep work-session memory local-only.

6. **Verify** (read-only, no cost):
   ```bash
   python3 -m gardener status              # shows pending transcripts + candidates_pending
   git -C ~/.claude/memory log --oneline   # projects land here as the run processes them
   tail ~/.../run.err.log                  # should stay empty
   ```
   Smoke-test the routing without a full run: `~/.claude/gardener/bin/claude -p "reply: OK"`.

## Notes

- **Catch-up:** `setup.sh` adds `RunAtLoad` + a time-gate so a run missed while the machine was off/asleep/logged-out executes at the next login (not just on sleep-wake).
- **Safety:** the deny backstop blocks the agent from writing hooks/settings/plugins even under `bypassPermissions`; the stage-2 curator runs Bash-free. `GARDENER_NO_CURATE=1` disables skill/CLAUDE.md curation.
- **Kill switch / uninstall:** `launchctl bootout gui/$(id -u)/com.$(id -un).memory-gardener` (macOS) or `systemctl --user disable --now memory-gardener.timer` (Linux).
- See the repo `README.md` for the full model, env-var table, and design docs.
