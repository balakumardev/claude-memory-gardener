# 🌱 Memory Gardener

**An offline agent that tends [Claude Code](https://docs.claude.com/en/docs/claude-code)'s native auto-memory — so it stays accurate, deduplicated, and synced across every machine you work on.**

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/runtime%20deps-0-brightgreen)
![Tests](https://img.shields.io/badge/tests-77%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-black)

Claude Code already writes itself memory notes as you work and reloads them next session. But those notes only get written when Claude happens to decide to, they drift out of date, and they never leave the machine they were born on. **Memory Gardener** closes those three gaps without replacing anything native:

- **Completeness** — it sweeps your session transcripts *after the fact* and distills the durable facts that never got saved live.
- **Freshness** — it reconciles new facts against old ones, marking superseded entries instead of letting contradictions pile up.
- **Portability** — it relocates memory to a stable, git-backed store so the same knowledge follows you across laptops and servers.
- **Skill & instruction curation** — it grows your skill library and global `CLAUDE.md` from what sessions actually do: new skills from recurring workflows, trigger-description fixes when a skill *should* have fired but didn't, variant/stale updates to existing skills — every change an isolated, revertible git commit.

It is a thin layer **on top of** Claude Code's memory, not a replacement: the native loader still does all the reading and recall. The Gardener only writes.

---

## How it works

```
   live Claude Code sessions
            │  (native auto-memory, untouched)
            ▼
   ~/.claude/projects/<proj>/<uuid>.jsonl   ← transcripts pile up on disk
            │
            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  THE GARDENER  (offline · scheduled · runs `claude -p`)       │
   │                                                               │
   │  scan ───▶ distill ───▶ extract ───▶ reconcile ───▶ commit    │
   │  (mtime    (strip      (durable      (dedup /        (git)     │
   │   water-    noise,      facts via     supersede,                │
   │   mark)     ~90%        a cheap        never                    │
   │             smaller)    model)         delete)                  │
   └─────────────────────────────────────────────────────────────┘
            │
            ▼
   ~/.claude/memory/<project>/   ──git push──▶  private remote  ◀── other machines pull
            │
            ▼
   next session auto-loads the improved memory (native, free)
```

1. **Scan** — finds transcripts modified since the last run (a per-session mtime watermark), skipping sessions still in progress and the Gardener's own activity.
2. **Distill** — pure-Python, deterministic noise stripping: drops tool output, thinking blocks, and injected context, leaving a compact digest (~90% smaller) of what was actually said.
3. **Extract & reconcile** — one cheap `claude -p` call per project pulls durable facts (preferences, decisions, conventions, gotchas) and reconciles them against existing memory: skip duplicates, update with new detail, mark contradictions `[SUPERSEDED yyyy-mm-dd]` (never hard-delete), create genuinely new entries. Standing rules can be routed into the project's `CLAUDE.md`.
4. **Commit & sync** — every run is one git commit in the memory repo. `*.md merge=union` plus a regenerated index means two machines writing at once converge automatically — no human ever resolves a conflict.
5. **Curate (stage 2)** — per-project agents also tend `<repo>/.claude/skills/` and queue cross-project observations (`NEW` / `MISSED-TRIGGER` / `VARIANT` / `STALE`) into `~/.claude/memory/_curator/candidates.md`. When the queue is non-empty, a single curator agent — the only writer for global state — folds them into `~/.claude/CLAUDE.md` and `~/.claude/skills/`: a new global skill needs the same observation twice (or an explicit "always do X"), a missed trigger needs just one quoted phrasing to extend a skill's description. `~/.claude` becomes a whitelist git repo (only `CLAUDE.md` + `skills/` tracked), with your manual edits snapshotted separately (`chore: snapshot manual edits`) so every `curate: skills + CLAUDE.md` commit is exactly the curator's diff: `git -C ~/.claude revert <sha>` undoes any curate. Set `GARDENER_NO_CURATE=1` to disable stage 2 entirely.

## Design principles

- **Native is the backbone.** No parallel memory store, format, or loader. The native loader stays the only thing that reads memory into a session.
- **Deterministic where possible, LLM where necessary.** Mechanical noise-stripping is Python; only the semantic extraction is the model.
- **Git is the safety harness.** Letting an LLM edit your memory autonomously is only safe because every run is a reviewable, revertible commit.
- **Eventually consistent, never blocking.** A scheduled, unattended writer must never stall on a merge conflict — so it can't.
- **Zero runtime dependencies.** Pure Python standard library. (Tests use `pytest`.)

## Requirements

- Python 3.9+ (standard library only)
- [Claude Code](https://docs.claude.com/en/docs/claude-code) v2.1.59+ (native auto-memory)
- `git`
- macOS (launchd) or Linux (systemd) for scheduling

## Install

```bash
git clone https://github.com/balakumardev/claude-memory-gardener
cd claude-memory-gardener
./install.sh
```

`install.sh` resolves a stable system Python, runs the one-time migration of any existing native memory into the git-backed store (your originals are renamed `*.pre-migration.bak`, never deleted), and installs the scheduler (launchd on macOS, a systemd timer on Linux).

For the **home project** (a bare `~`), add one line to `~/.claude/settings.json` so Claude reads from the new location:

```json
{ "autoMemoryDirectory": "~/.claude/memory/home" }
```

## Usage

```bash
python3 -m gardener status    # read-only: what a run would process right now
python3 -m gardener run       # process new transcripts now
python3 -m gardener migrate   # one-time relocation of existing native memory
```

Or just let the scheduler run it a few times a day. Watch the first run's `git -C ~/.claude/memory diff` to see what it distills before trusting it unattended.

## Custom model & MCP routing

By default the Gardener runs `claude` with the `haiku` model and no MCP servers. You can point it at a different model, endpoint, binary, or a scoped set of MCP servers entirely through environment variables — no code changes — by exporting them in whatever launches the run (your launchd/systemd unit, or a wrapper script):

| Env var | Effect | Default |
|---|---|---|
| `GARDENER_MODEL` | value passed to `--model` | `haiku` |
| `GARDENER_CLAUDE_BIN` | path/name of the `claude` binary | `claude` |
| `GARDENER_MCP_CONFIG` | path to an MCP config; when set, runs `--strict-mcp-config --mcp-config <path>` so **only** those servers load (a background run shouldn't boot your heavy project MCP servers) | none |
| `GARDENER_TOOLS_EXTRA` | extra tool name(s) appended to `--tools`, e.g. an MCP tool | none |
| `GARDENER_EXTRA_ARGS` | extra flags appended verbatim | none |
| `GARDENER_CURATOR_MODEL` | model for the stage-2 curator (skills/global-CLAUDE.md judgment); falls back to `GARDENER_MODEL` | `GARDENER_MODEL` |
| `GARDENER_NO_CURATE` | set to `1` to disable stage-2 curation and the `~/.claude` kit repo entirely | unset |

Any `ANTHROPIC_*` provider env (base URL, key, model aliases) is passed through to the `claude` subprocess, so routing through an Anthropic-compatible proxy works the same way.

**Example** — route the Gardener through an OpenAI/GLM-style proxy and expose only a code-index MCP server:

```sh
# in your scheduler's environment / wrapper:
export ANTHROPIC_BASE_URL="https://your-proxy.example"
export ANTHROPIC_API_KEY="sk-..."
export GARDENER_MODEL="your-model-id"
export GARDENER_MCP_CONFIG="$HOME/.config/gardener/mcp.json"   # {"mcpServers": {"code-index": {...}}}
export GARDENER_TOOLS_EXTRA="mcp__code-index__search"
python3 -m gardener run
```

## Cross-machine sync

Point the memory repo at a **private** remote (your memory is personal — keep the remote private):

```bash
git -C ~/.claude/memory remote add origin <your-private-remote>
git -C ~/.claude/memory push -u origin main
```

Each machine runs its own Gardener, pulls before processing and pushes after. Because memory keys are home-relative logical names (`~/.claude/memory/<project>`), they resolve identically on every machine and OS — a Mac and a Linux box share the same memory without path collisions. Raw transcripts never leave the machine; only distilled memory syncs.

## How it's built

A small, focused Python package — each module has one responsibility and is independently tested:

| Module | Responsibility |
|---|---|
| `scanner` · `watermark` | Find new transcripts; crash-safe per-session progress |
| `distiller` | Deterministic transcript → digest noise strip |
| `agent` · `prompts/` | The single `claude -p` extraction/reconciliation step |
| `memindex` | Regenerate the `MEMORY.md` index |
| `gitmemory` | Bootstrap, union-merge, scale-guard, push-retry |
| `resolver` | Stable logical-name keys + `autoMemoryDirectory` pointers |
| `runner` | Orchestrate the pipeline; fail-open per project; stale-lock recovery |
| `skillindex` | Deterministic inventory of global skills (missed-trigger detection input) |
| `curator` | Stage-2 agent: single writer for global skills + global `CLAUDE.md` |
| `migrate` | One-time lossless relocation of existing memory |

```bash
python3 -m pytest    # 77 tests, standard library + pytest only
```

## License

MIT © Bala Kumar
