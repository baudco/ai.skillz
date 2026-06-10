# `/branch-in-term` — reference notes

Background research on Claude Code's session-branching + extensibility
surface, captured while building this command. Verified against the
official docs (`code.claude.com/docs`). Kept for later reference.

## TL;DR

Fork the current session into a new terminal. The **active impl** is a
**bash prompt-command** (`branch-in-term.md`): when invoked it asks
Claude to run a `setsid … claude --resume <id> --fork-session` spawn
**via the Bash tool**. Session id:

- **precise**: fork the *exact* current session by id, read from
  `.claude/.current_session` (stashed by a `SessionStart` hook).
- **fallback** (`--continue`): fork the *most-recent* session in cwd —
  no hook, but can grab the wrong one.

A modden-aware **xonsh alias** (`branch-in-term.xsh`) exists but is
**optional/experimental** — not wired into the command (see below).

## The `!`-exec gotcha (the headline learning)

Two corrections, in order of how much they bit:

1. Slash commands DO support inline bash via the **`!` prefix** (a
   guide agent wrongly said "commands can't run shell — they're just
   prompts"; that conflates them with `SKILL.md` Skills). The `!`…``
   runs at invocation and its stdout is injected into context.
2. **BUT `!`-exec can only run *analyzable, read-only-ish* commands.**
   Claude Code's static command-safety analyzer **hard-blocks process
   spawners** — `setsid`, `xonsh -c`, `nohup`, `env`, anything that
   "runs its argument as a command — cannot be statically analyzed."
   `allowed-tools` does NOT override it (it's the allow-list-bypass
   guard). So a slash-command `!`-exec **cannot spawn a terminal**.

Where spawning *does* work:
- the **Bash tool** (Claude executes it; may prompt to approve) → the
  prompt-command route this command uses;
- a **user-initiated input-box `!`** (`! setsid -f alacritty -e …`) →
  runs in your own shell, no analyzer.

## modden integration (optional / future — via the `.xsh` alias)

modden exports onto every spawned child (see
`modden.runtime.term` / `modden.runtime.env`):

- **`$_MODDEN_RT_VARS`** — a `str(dict)` (parse with
  `ast.literal_eval`) holding `bigd_pid`, `bigd_winid`,
  `bigd_term_sid`, **`bigd_alacritty_socket`**, `tractor_rtvars`.
- **`$MODDEN_SID`** — the spawn's unique UUID.

So inside a modden workspace the alias opens the fork as a **sibling
window in the same alacritty tree** — the exact mechanism modden uses
for sub-terminals:

```
alacritty msg -s <bigd_alacritty_socket> create-window \
  --working-directory <cwd> --title claude:branch \
  -e claude --resume <id> --fork-session
```

That lets the WM place the new window in the workspace instead of a
detached standalone one. (modden does placement via alacritty's
daemon/socket, not i3/sway IPC.) Outside modden → `$TERMINAL -e …`.

## Verified facts

- **Slash command file**: `.claude/commands/<name>.md`; frontmatter
  `description`, `allowed-tools`, `argument-hint`, `model`,
  `disable-model-invocation`; `$ARGUMENTS` / `$1`..`$9`; `@file`
  mentions; **`!`cmd`` bash-exec** (needs `allowed-tools` w/ the Bash
  tool). Output of `!` is embedded before the turn is sent — but ONLY
  for analyzable commands; process spawners are blocked (see gotcha
  above).
- **Session id at runtime**: NOT exposed as an env var to command
  bodies. **Hooks** get it on stdin (`session_id`) plus
  `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`;
  `$CLAUDE_PROJECT_DIR` is set for hook commands.
- **Programmatic fork**: `claude --resume <id> --fork-session` and
  `claude --continue --fork-session`. There is **no documented way to
  capture the NEW forked session's UUID** programmatically (it's
  printed, not emitted structured). The precise variant avoids
  needing it by forking a *known* id.
- **Hook events**: `SessionStart`, `SessionEnd`, `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `PreCompact`,
  `Notification`. Configured in `settings.json` under `hooks` with
  `matcher` + `command`.

## Packaging / distribution

For sharing, wrap the command (+ hook + `.xsh`) as a Claude Code
**plugin**: `.claude-plugin/plugin.json` + `commands/<name>.md` +
`hooks/hooks.json`. Or deploy via `deploy-skill.sh command
branch-in-term <repo>` (symlink + gitignore + hook hint).

## Doc references

- Slash commands (incl. `!` bash-exec + `allowed-tools`):
  `code.claude.com/docs/en/slash-commands.md`
- Sessions / `--continue|--resume --fork-session`:
  `…/sessions.md`
- Hooks (stdin `session_id`/`transcript_path`, events, config):
  `…/hooks.md`
- Plugins: `…/plugins.md`, `…/plugins-reference.md`
- Checkpointing (Esc-Esc rewind menu: restore conversation/code):
  `…/checkpointing.md`
- modden runtime env / termman: `modden/runtime/env.py`
  (`_MODDEN_RT_VARS`), `modden/runtime/term.py` (`alacritty msg
  create-window`).
