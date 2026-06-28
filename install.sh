#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"

# Prefer a stable, non-virtualenv python3 for the long-lived scheduler unit.
# The package is stdlib-only, so any python3 >= 3.9 works; we just avoid a
# transient venv/conda/pyenv interpreter that may later be deleted.
pick_python() {
  local p
  for p in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
  command -v python3
}
PYTHON="$(pick_python)"
case "$PYTHON" in
  *"/.venv/"*|*"/venv/"*|*"/envs/"*|*"/shims/"*|"${VIRTUAL_ENV:-/nonexistent}"/*)
    echo "WARNING: resolved python3 looks like a virtualenv: $PYTHON" >&2
    echo "         The scheduler will use this interpreter permanently; if this env" >&2
    echo "         is later removed, scheduled runs will fail. Consider installing a" >&2
    echo "         system python3 and re-running." >&2
    ;;
esac
echo "Repo: $REPO"
echo "Using Python: $PYTHON"

echo ">> Running one-time migration..."
( cd "$REPO" && "$PYTHON" -m gardener migrate ) || { echo "migration failed; aborting install" >&2; exit 1; }

echo
echo ">> MANUAL STEP (one line you must add yourself):"
echo "   Your ~/.claude/settings.json is permission-locked, so add this key:"
echo '     "autoMemoryDirectory": "~/.claude/memory/home"'
echo

OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.balakumar.memory-gardener.plist"
  sed -e "s#__PYTHON__#$PYTHON#g" -e "s#__REPO__#$REPO#g" \
    "$REPO/scheduler/com.balakumar.memory-gardener.plist" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo ">> launchd agent installed: $PLIST"
elif command -v systemctl >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  sed -e "s#__PYTHON__#$PYTHON#g" -e "s#__REPO__#$REPO#g" \
    "$REPO/scheduler/memory-gardener.service" > "$HOME/.config/systemd/user/memory-gardener.service"
  cp "$REPO/scheduler/memory-gardener.timer" "$HOME/.config/systemd/user/memory-gardener.timer"
  systemctl --user daemon-reload
  systemctl --user enable --now memory-gardener.timer
  echo ">> systemd timer installed and enabled."
else
  echo "No supported scheduler (launchd/systemd) found. Run '$PYTHON -m gardener run' from cron, or invoke 'garden' manually." >&2
fi

echo
echo ">> To set up cross-machine sync, add a PRIVATE remote and push:"
echo "   git -C ~/.claude/memory remote add origin <your-private-remote-url>"
echo "   git -C ~/.claude/memory push -u origin main"
echo ">> Add an alias to your shell rc:  alias garden='( cd $REPO && $PYTHON -m gardener run )'"
