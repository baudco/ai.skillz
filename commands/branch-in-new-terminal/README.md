# `/branch-in-new-terminal` — reference notes

Background research on Claude Code's session-branching + extensibility
surface, captured while building this command. Verified against the
official docs (`code.claude.com/docs`). Kept for later reference.

## TL;DR

A custom **slash command** can run a shell side-effect at invocation
(via the `!` prefix), so `/branch-in-new-terminal` just spawns a new
terminal running `claude … --fork-session`. Two variants:

- **precise** (this command's default): fork the *exact* current
  session by id — needs a `SessionStart` hook to stash the id.
- **fallback** (`--continue --fork-session`): fork the *most-recent*
  session in cwd — no hook, but can grab the wrong one.

## Key correction (a guide agent got this wrong)

A first pass conflated **slash commands** with **Skills** and claimed
command files "can't execute shell — they're just prompts." That's
wrong:

- `.claude/commands/<name>.md` **slash commands** DO support inline
  bash via the **`!` prefix**, with an `allowed-tools` declaration.
  The `!`…`` runs at invocation and its stdout is injected into
  context. This is the mechanism this command relies on.
- `.claude/skills/<name>/SKILL.md` **Skills** are the model-invoked
  capabilities (no `!` exec); a different thing.

## The clean approach (fallback variant)

A pure slash command, no hook, no session-id plumbing:

```markdown
---
description: Fork this session into a new terminal window
allowed-tools: Bash(setsid:*)
---
!`setsid -f "${TERMINAL:-alacritty}" -e claude --continue --fork-session >/dev/null 2>&1 & echo "forked → new terminal"`
```

Why it sidesteps the session-id problem: `claude --continue
--fork-session` resumes the **most-recent session in cwd** (which IS
this one) and forks it — you never need to capture the current UUID.
(`--continue --fork-session` is documented in the sessions docs.)

Caveat: "most-recent in cwd" is only ambiguous if you started another
session in this dir in the interim.

## The precise-session variant (this command's default)

To fork a *specific* session rather than "most recent," use a hook —
**only hooks get the session id**. A `SessionStart` hook receives
`{session_id, transcript_path, cwd, …}` on stdin; stash it, then the
command reads it:

```jsonc
// settings.json
{"hooks": {"SessionStart": [{"matcher": "*", "hooks": [
  {"type": "command",
   "command": "mkdir -p \"$CLAUDE_PROJECT_DIR/.claude\" && stash=\"$CLAUDE_PROJECT_DIR/.claude/.current_session\" && rm -f \"$stash\" && session_id=\"$(jq -er '.session_id | select(type == \"string\" and length > 0)')\" && tmp=\"$(mktemp \"$stash.XXXXXX\")\" && printf '%s\\n' \"$session_id\" > \"$tmp\" && mv \"$tmp\" \"$stash\""}
]}]}}
```
```markdown
<!-- command body -->
!`setsid -f "${TERMINAL:-alacritty}" -e claude --resume "$(cat .claude/.current_session)" --fork-session & echo opening`
```

## Verified facts

- **Slash command file**: `.claude/commands/<name>.md`; frontmatter
  `description`, `allowed-tools`, `argument-hint`, `model`,
  `disable-model-invocation`; `$ARGUMENTS` / `$1`..`$9`; `@file`
  mentions; **`!`cmd`` bash-exec** (needs `allowed-tools` w/ the Bash
  tool). Output of `!` is embedded before the turn is sent.
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
  `matcher` + `command`. Hooks run in your shell, so a hook *can*
  spawn a terminal too (but fires unconditionally — a command is the
  on-demand trigger).

## The modden-termman angle 😎

Both variants reduce to "spawn a process running `claude …
--fork-session`." Swap the bare `setsid $TERMINAL -e …` for a call
into **modden's terminal-manager** to get WM-aware placement (i3/sway)
for free:

```markdown
!`mod term open --title 'claude:branch' --cmd 'claude --resume "$(cat .claude/.current_session)" --fork-session'`
```

Longer term: termman tags the branch terminal (title from
`$ARGUMENTS`) and splits it beside the current pane in the active
layout. The slash command is just the trigger; termman does placement.

## Packaging / distribution

For sharing, wrap the command (+ hook) as a Claude Code **plugin**:
`.claude-plugin/plugin.json` + `commands/<name>.md` + `hooks/hooks.json`.
The plugin is the right vehicle for installable-across-machines.

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
