# Sidecar `claude` session — user-driven REPL feeding back to main session

## Context

When working with a main `claude` session on a long debugging
flow (e.g. tractor's MTF stabilization), it's useful to dump
test-run output, py-spy snapshots, or quick analysis questions
to a SEPARATE `claude` session you drive *yourself* in another
terminal — without interrupting the UX of the main session.

The sidecar's findings should surface back to the main session
"transparently" (no manual paste, no context-switch tax).

Native Claude Code does NOT support this directly:
- No `claude --attach-subagent <uuid>` flag.
- `--resume <session-id>` lets one client pick up a session, but
  not two clients drive it concurrently.
- The Agent tool runs subagents synchronously inside the main
  session — they're MY children, not yours.
- MCP is a tool layer, not a cross-session message bus
  (without a custom server).
- SDK Managed Agents support coordinator→subagent threads but
  none of those threads accept interactive user input.

So the workflow has to be built from third-party pieces.

## Recommended stack (built today)

**`tmux` (or `zellij`) + sidecar `claude` + shared-file inbox +
`Monitor` watching `tail -F` on the main side.**

### Layout

```
tmux (or zellij) session
├── pane 0: main `claude`  (the working session — me)
└── pane 1: sidecar `claude`  (you drive directly)
                ↓ writes findings to
        .claude/sidecar/findings.md
                ↑ tail -F watched by `Monitor` on main side
```

### Wiring steps

1. **Create the inbox**:
   ```sh
   mkdir -p .claude/sidecar
   touch .claude/sidecar/findings.md
   ```

2. **Sidecar pin-prompt** (paste at start of sidecar session):
   > "You are a sidecar analysis session. After every meaningful
   > finding (test-run summary, py-spy classification, etc.) APPEND
   > a structured markdown entry to
   > `/abs/path/.claude/sidecar/findings.md` using atomic temp+mv:
   > write to `findings.md.tmp` then `mv findings.md.tmp findings.md`
   > (no — append, so use a temp+`cat >> mv` pattern, or just
   > `>> findings.md` if collisions don't matter). Each entry: a
   > `## YYYY-MM-DDThh:mm:ss <topic>` H2, then the body."

3. **Main side — start `tail -F` as a bg `Bash`** with
   `run_in_background=true`, then attach `Monitor` to it so each
   appended line surfaces as a notification mid-conversation. No
   polling.

4. **Result**: you converse with the sidecar in pane 1 normally.
   When it appends a finding, I (main session) get pushed the new
   line and can integrate it without you pasting.

### Atomicity gotchas

- Pure `>> findings.md` is fine for line-appended markdown if
  there's only one writer. POSIX guarantees writes ≤ PIPE_BUF
  (≥512 bytes) are atomic for append-mode FDs.
- Larger writes (multi-paragraph findings): write to
  `findings.md.tmp.$$`, then `cat findings.md.tmp.$$ >> findings.md
  && rm findings.md.tmp.$$`. The append is the only racy step.
- If main session needs to ACK / consume entries (so they're not
  re-shown later), maintain a `findings.md.cursor` file with a
  byte offset. `tail -c +$(cat cursor)` reads only new bytes.

## Lighter-weight alternatives

- **`llm` CLI (Simon Willison)**, `pip install llm`:
  - `pytest … 2>&1 | llm -m claude-opus-4 'classify failures'`
  - All conversations logged to
    `~/.config/io.datasette.llm/logs.db` (SQLite).
  - Main session can `sqlite3 logs.db "SELECT response FROM
    responses ORDER BY id DESC LIMIT 5"` on demand.
  - No persistent REPL. Good for *dump* style, not *chat* style.

- **`gptme`** (github.com/ErikBjare/gptme): Claude-Code-flavored
  CLI with tools, lighter, multi-conversation. Same shared-file
  trick works.

- **`aichat`** (github.com/sigoden/aichat): popular Rust TUI;
  first-class session/log management; shared session files
  readable by main side.

## Heaviest, also nicest — custom MCP message-bus

A ~80-line Python MCP server exposing:

- `post_finding(channel: str, body: str) -> id`
- `read_findings(channel: str, since: int = 0) -> list[entry]`

Both `claude` sessions add it as an MCP server in
`.claude/settings.json`. Real cross-session messaging via tool
calls, no file watching, structured payloads, queryable history.
Worth building if this pattern recurs across projects; overkill
for a one-off.

Storage: SQLite, single file. Concurrency: WAL mode handles two
readers/writers cleanly.

## Decision matrix

| Option | Setup time | Interactive REPL | Push to main | Structured |
|---|---|---|---|---|
| tmux + claude sidecar + tail+Monitor | ~2 min | ✓ | ✓ | text only |
| `llm` CLI piped | ~30 sec | ✗ | poll only | rows in SQLite |
| `gptme` / `aichat` | ~5 min | ✓ | poll only | text |
| custom MCP bus | ~1 hr | ✓ | tool-call | full schema |

## Future direction

- A Claude Code feature request worth filing: `claude
  --attach-bus <socket>` that lets two sessions both connect to a
  shared message bus exposed by the harness itself, with proper
  session-scoping (so only sibling sessions in the same workspace
  see each other). Until then, the MCP-bus pattern emulates this.

- Possible `ai.skillz` skill: `sidecar` skill that scaffolds
  `.claude/sidecar/{inbox.md,cursor,sidecar-prompt.md}`, adds the
  sidecar pin-prompt as a template, and emits a one-liner to start
  the `tail -F`+`Monitor` watch from the main side.
