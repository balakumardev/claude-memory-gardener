#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# Memory Gardener — full turnkey setup for any Mac (or Linux).
#
# Installs the complete runtime that the minimal install.sh does not:
#   • a `claude` routing/isolation SHIM      -> ~/.claude/gardener/bin/claude
#   • a deny-rule safety BACKSTOP            -> ~/.claude/gardener-config/settings.json
#   • the scheduler entrypoint with CATCH-UP -> ~/.claude/gardener/run.sh
#   • the launchd job with RunAtLoad         -> ~/Library/LaunchAgents/com.<user>.memory-gardener.plist
#   • a one-time memory migration + local git-backed memory store
#
# Safe to re-run: it updates generated files (shim, run.sh, plist) but never
# clobbers your own gardener.env (model routing) or a customized gardener-config.
#
# After it runs, edit ~/.claude/gardener/gardener.env to point the gardener at a
# CHEAP model (see the examples in that file) — otherwise batch gardening uses
# your normal `claude` auth + default model.
# ============================================================================
REPO="$(cd "$(dirname "$0")" && pwd)"
GDIR="$HOME/.claude/gardener"
CFGDIR="$HOME/.claude/gardener-config"
LABEL="com.$(id -un).memory-gardener"

# ── Pick a stable, non-virtualenv python3 (stdlib-only pkg; avoid transient venv) ──
pick_python() {
  local p
  for p in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
  command -v python3
}
PYTHON="$(pick_python)"
case "$PYTHON" in
  *"/.venv/"*|*"/venv/"*|*"/envs/"*|*"/shims/"*)
    echo "WARNING: python3 looks like a virtualenv ($PYTHON); a scheduled unit that" >&2
    echo "         outlives it will break. Prefer a system python3." >&2 ;;
esac

# ── Find the real `claude` (the shim must call it by absolute path) ──
REAL_CLAUDE="$(command -v claude || true)"
[ -z "$REAL_CLAUDE" ] && [ -x "$HOME/.local/bin/claude" ] && REAL_CLAUDE="$HOME/.local/bin/claude"
if [ -z "$REAL_CLAUDE" ]; then
  echo "ERROR: could not find a 'claude' binary on PATH or at ~/.local/bin/claude." >&2
  echo "       Install Claude Code first, then re-run." >&2
  exit 1
fi

# ── Node bin dir (only needed if you use node-based MCP servers like auggie) ──
NODE_BIN=""
if command -v node >/dev/null 2>&1; then NODE_BIN="$(dirname "$(command -v node)"):"; fi

echo "Repo:    $REPO"
echo "Python:  $PYTHON"
echo "claude:  $REAL_CLAUDE"
echo "Label:   $LABEL"

mkdir -p "$GDIR/bin" "$CFGDIR"

# ── (1) Shim (generated; always refreshed) ──
sed "s#__REAL_CLAUDE__#$REAL_CLAUDE#g" "$REPO/setup/gardener-shim.sh" > "$GDIR/bin/claude"
chmod +x "$GDIR/bin/claude"
echo ">> shim installed: $GDIR/bin/claude"

# ── (2) gardener.env (routing) — never clobber the user's real one ──
if [ ! -f "$GDIR/gardener.env" ]; then
  cp "$REPO/setup/gardener.env.example" "$GDIR/gardener.env"
  chmod 600 "$GDIR/gardener.env"
  echo ">> gardener.env seeded from example (EDIT IT to route to a cheap model)"
else
  echo ">> gardener.env exists — left as-is"
fi

# ── (3) Deny-rule backstop — never clobber a customized one ──
if [ ! -f "$CFGDIR/settings.json" ]; then
  cp "$REPO/setup/gardener-config-settings.json" "$CFGDIR/settings.json"
  echo ">> deny backstop installed: $CFGDIR/settings.json"
else
  echo ">> gardener-config/settings.json exists — left as-is"
fi

# ── (4) run.sh (generated; always refreshed) ──
sed -e "s#__PYTHON__#$PYTHON#g" -e "s#__REPO__#$REPO#g" -e "s#__NODE_BIN__#$NODE_BIN#g" \
  "$REPO/setup/run.sh.template" > "$GDIR/run.sh"
chmod +x "$GDIR/run.sh"
echo ">> run.sh installed (with catch-up gate): $GDIR/run.sh"

# ── (5) One-time migration of any existing native memory ──
echo ">> running one-time migration..."
( cd "$REPO" && "$PYTHON" -m gardener migrate ) || { echo "migration failed; aborting" >&2; exit 1; }

# ── (6) Scheduler ──
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  sed -e "s#__LABEL__#$LABEL#g" -e "s#__RUNSH__#$GDIR/run.sh#g" -e "s#__REPO__#$REPO#g" \
    "$REPO/setup/memory-gardener.plist.template" > "$PLIST"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"
  echo ">> launchd agent installed + loaded (RunAtLoad triggers a first run now): $PLIST"
elif command -v systemctl >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/memory-gardener.service" <<EOF
[Unit]
Description=Memory Gardener run
[Service]
Type=oneshot
ExecStart=$GDIR/run.sh
EOF
  cat > "$HOME/.config/systemd/user/memory-gardener.timer" <<EOF
[Unit]
Description=Memory Gardener schedule (with catch-up)
[Timer]
OnCalendar=*-*-* 03:17,13:47,20:23
Persistent=true
[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now memory-gardener.timer
  echo ">> systemd timer installed + enabled (Persistent=true catches up missed runs)."
else
  echo "No launchd/systemd found. Run '$GDIR/run.sh' from cron, or invoke it manually." >&2
fi

cat <<EOF

Done. Next steps:
  1. Route to a cheap model:   \$EDITOR ~/.claude/gardener/gardener.env
  2. (home project memory) add to ~/.claude/settings.json:
       "autoMemoryDirectory": "~/.claude/memory/home"
  3. Watch the first run:      git -C ~/.claude/memory log --oneline
  4. (optional) cross-machine sync — add a PRIVATE remote to ~/.claude/memory
     (skip this on a work machine to keep work memory local-only).
  5. Kill switch for skill/CLAUDE.md curation: GARDENER_NO_CURATE=1 in gardener.env
EOF
