# `commands/` + `/branch-in-term` — summary

Added a reusable slash-**commands** layer to `ai.skillz` (peer to
`skills/`) and the first command, `/branch-in-term` (fork the current
Claude Code session into a new terminal).

- **`commands/<name>/`** layout (`.md` + `DEPLOY.md` + `README.md` +
  optional `*.hook.json` / `<name>.xsh`); deployed as a flat
  `.claude/commands/<name>.md` symlink.
- **`deploy-skill.sh command <name|all> <repo> [--global]`** — new
  deploy mode (symlink + gitignore merge + hook hint).
- **`/branch-in-term`** = a **bash prompt-command** (Claude runs
  `setsid … claude --resume "$(cat .claude/.current_session)"
  --fork-session` via the Bash tool). A `SessionStart` hook stashes
  the exact session id → `.claude/.current_session`.

**Headline learning:** a slash-command inline `!`-exec **cannot spawn
a terminal** — Claude Code's static analyzer hard-blocks process
spawners (`setsid`, `xonsh -c`, …); `allowed-tools` doesn't override
it. Spawning only works via the Bash tool or a user-initiated
input-box `!`. (Earlier "it works" was a Bash-tool test, not the
`!`-exec.)

**Deferred:** a modden-aware xonsh alias (`branch-in-term.xsh`) that
opens the fork as a WM-placed sibling window via
`alacritty msg -s $bigd_alacritty_socket create-window` (socket from
`$_MODDEN_RT_VARS`). Optional follow-up: a fixed-path wrapper script,
allow-listed by exact path, to make the `/` command frictionless.

Full notes: `branch-in-term-cmds-plan.md`.
