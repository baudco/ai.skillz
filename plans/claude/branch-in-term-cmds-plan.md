# `commands/` area + `/branch-in-term` — session export

Handoff/continuation notes from the session that added a reusable
slash-**commands** layer to `ai.skillz` and built the first command,
`/branch-in-term`. Mirrors the `plans/claude/` convention.

## Context

We wanted a `/branch-in-term` command that forks the current Claude
Code session into a new terminal (`claude --resume <id>
--fork-session`) so a side-branch conversation opens in its own
window. Along the way we added a general `commands/` deployment area
(peer to `skills/`) and taught `deploy-skill.sh` about it.

The original tractor-side work this branched from was a `tractor.log`
fix (`get_logger()` sub-package granularity: `devx.debug` no longer
collapses to `devx`) — unrelated to the commands work but the same
session.

## What was built (all under `~/repos/ai.skillz/`)

- **`commands/` area** — peer to `skills/`. Each command lives in
  `commands/<name>/` with `<name>.md` (the command, deployed as a flat
  `.claude/commands/<name>.md` symlink), `DEPLOY.md`, `README.md`, and
  optional companions (`*.hook.json`, `<name>.xsh`). Indexed in
  `commands/README.md`.
- **`commands/branch-in-term/`**:
  - `branch-in-term.md` — the command. **Now a bash prompt-command**
    (Claude runs the `setsid … claude --resume … --fork-session` spawn
    via the Bash tool). Title from `$ARGUMENTS`.
  - `session-stash.hook.json` — a `SessionStart` hook:
    `jq -r .session_id > "$CLAUDE_PROJECT_DIR/.claude/.current_session"`
    — the explicit-session-id source the command reads.
  - `branch-in-term.xsh` — **optional/experimental** modden-aware
    xonsh alias (see "deferred").
  - `DEPLOY.md` / `README.md`.
- **`scripts/deploy-skill.sh` `command` mode** —
  `deploy-skill.sh command <name|all> <repo> [--method …] [--global]`.
  Symlinks the `.md` into `.claude/commands/` (absolute, or
  submodule-relative `../ai.skillz/commands/<name>/<name>.md`),
  `--global` → `~/.claude/commands/`, merges the command's gitignore
  patterns, prints a hook hint, and lists commands in `--help`.
- **`gitignore-patterns.conf`** — new `[branch-in-term]` section
  (`.claude/.current_session`).

## Key decisions & the `!`-exec gotcha (headline learning)

- **A slash-command `!`-exec CANNOT spawn a terminal.** Claude Code's
  static command-safety analyzer hard-blocks process spawners
  (`setsid`, `xonsh -c`, `nohup`, …): *"runs its argument as a command
  — cannot be statically analyzed."* `allowed-tools` does not override
  it. Spawning works only via (a) the **Bash tool** (Claude runs it;
  may prompt) or (b) a **user-initiated input-box `!`** (own shell, no
  analyzer).
- A misleading "live test" earlier ran the spawn via the *Bash tool*,
  not the slash-command `!`-exec — so it *looked* like the bash
  `!`-exec version worked. It never could.
- `claude` CLI supports `-r/--resume`, `-c/--continue`,
  `--fork-session`. There's **no documented way to capture the NEW
  forked session's UUID** → fork a *known* id (the hook's stash).
- `xonsh -c` **does** load `XONSHRC` (alias is found + runs), so a
  xonsh-alias path is viable; deferred for now.

## modden integration (deferred — `branch-in-term.xsh`)

modden exports onto every spawned child (`modden/runtime/term.py`,
`modden/runtime/env.py`):
- `$_MODDEN_RT_VARS` — a `str(dict)` (`ast.literal_eval`) with
  `bigd_pid`, `bigd_winid`, `bigd_term_sid`, **`bigd_alacritty_socket`**,
  `tractor_rtvars`.
- `$MODDEN_SID` — the spawn's UUID.

Inside a modden workspace, the alias opens the fork as a **sibling
window in the same alacritty tree** — modden's own sub-terminal call:
`alacritty msg -s <bigd_alacritty_socket> create-window
--working-directory <cwd> --title … -e claude --resume <id>
--fork-session`. Outside modden → standalone `$TERMINAL -e …`. The
`.xsh` reads all env via the xonsh `Env` (`@.env` / `__xonsh__.env`).

## Current state

- **Works**: `deploy-skill.sh command …` (symlink + gitignore + hook
  hint); the `SessionStart` hook (writes `.current_session`); the
  `.xsh` alias from a real shell (parses + registers + spawns).
- **Reworked**: `branch-in-term.md` is now a prompt-command (the
  `!`-exec / xonsh-`!`-exec versions failed the analyzer).
- **Deferred**: wiring the slash-command to the modden-aware xonsh
  alias.

## Next steps

1. Use `/branch-in-term [title]` → approve the Bash spawn (or use the
   input-box `!` form for zero friction).
2. (frictionless `/`) add a fixed-path wrapper `branch-in-term-fork.sh`
   (does the `setsid` spawn) and allow-list it by exact path
   (`Bash(/abs/.../branch-in-term-fork.sh)`) so the prompt-command
   stops prompting. The same script also serves `! branch-in-term-fork`.
3. (later) revisit the modden-aware `.xsh` path for WM-placed sibling
   windows; decide how the `/` command reaches it given the analyzer.
4. teach `deploy-skill.sh` to also (optionally) merge the companion
   hook into `settings.json` (currently manual).
