#!/usr/bin/env bash
# Memory Gardener `claude` shim  —  installed to ~/.claude/gardener/bin/claude
# and put FIRST on PATH by run.sh, so the background gardener's `claude` calls
# route through here instead of your interactive Claude Code.
#
# What it does (all optional bits are driven by ~/.claude/gardener/gardener.env):
#   1. Isolation — sets CLAUDE_CONFIG_DIR to ~/.claude/gardener-config so the
#      gardener does NOT inherit your interactive hooks/notifications, and the
#      deny-rule backstop in that config's settings.json takes effect.
#   2. Model routing — source gardener.env to point the gardener at a cheap
#      model / proxy (so 3x/day batch gardening doesn't burn your main budget).
#   3. Local router pre-warm — if GARDENER_CCR_LABEL + GARDENER_CCR_PORT are set,
#      make sure that loopback router (e.g. claude-code-router) is up first.
#   4. MCP — if ~/.claude/gardener/mcp.json exists, load ONLY those servers
#      (--strict-mcp-config) and append GARDENER_MCP_TOOL to --tools.
#   5. A wall-clock guard so one hung project can't wedge the whole run.
#
# This file is generated from setup/gardener-shim.sh by setup.sh, which
# substitutes __REAL_CLAUDE__ with the absolute path to your real `claude`.
set -uo pipefail
[ -f "$HOME/.claude/gardener/gardener.env" ] && . "$HOME/.claude/gardener/gardener.env"
export CLAUDE_CONFIG_DIR="$HOME/.claude/gardener-config"
REAL_CLAUDE="${GARDENER_CLAUDE_REAL:-__REAL_CLAUDE__}"
MCP_CFG="$HOME/.claude/gardener/mcp.json"

# (3) Optional: ensure a local loopback model router is running (CCR-style).
if [ -n "${GARDENER_CCR_LABEL:-}" ] && [ -n "${GARDENER_CCR_PORT:-}" ]; then
  _url="http://127.0.0.1:${GARDENER_CCR_PORT}/"
  _curl=(env -u http_proxy -u HTTP_PROXY -u https_proxy -u HTTPS_PROXY -u all_proxy -u ALL_PROXY NO_PROXY=127.0.0.1 curl)
  if ! "${_curl[@]}" -fsS --max-time 2 "$_url" >/dev/null 2>&1; then
    launchctl kickstart -k "gui/$(id -u)/${GARDENER_CCR_LABEL}" >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do
      "${_curl[@]}" -fsS --max-time 1 "$_url" >/dev/null 2>&1 && break
      sleep 0.25
    done
  fi
fi

# (2)+(4) Rebuild argv: optionally strip --model (when a proxy/router decides
# the model via gardener.env), and append the MCP tool to --tools.
args=(); prev=""
for a in "$@"; do
  if [ "$prev" = "--model" ]; then
    prev=""
    [ -n "${GARDENER_STRIP_MODEL:-}" ] || args+=("--model" "$a")
    continue
  fi
  if [ "$prev" = "--tools" ]; then
    prev=""
    if [ -n "${GARDENER_MCP_TOOL:-}" ]; then args+=("$a,${GARDENER_MCP_TOOL}"); else args+=("$a"); fi
    continue
  fi
  case "$a" in
    --model) prev="--model" ;;
    --tools) prev="--tools"; args+=("--tools") ;;
    *) args+=("$a") ;;
  esac
done

mcp_args=()
[ -f "$MCP_CFG" ] && mcp_args=(--strict-mcp-config --mcp-config "$MCP_CFG")

# (5) Run with a wall-clock guard (default 30 min; override GARDENER_GUARD_SECONDS).
"$REAL_CLAUDE" "${mcp_args[@]}" "${args[@]}" &
cpid=$!; ( sleep "${GARDENER_GUARD_SECONDS:-1800}"; kill "$cpid" 2>/dev/null ) & gpid=$!
wait "$cpid"; rc=$?; kill "$gpid" 2>/dev/null || true
exit "$rc"
