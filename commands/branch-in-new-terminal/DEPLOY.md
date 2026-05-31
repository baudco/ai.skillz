# Deploying `/branch-in-new-terminal`

A custom Claude Code **slash command** that forks the current
conversation (`claude --resume <id> --fork-session`) and opens the
branch in a new terminal window. Unlike skills, commands deploy as a
flat `.md` file under `.claude/commands/`.

Two pieces:
1. the **command** file → `.claude/commands/branch-in-new-terminal.md`
2. a **`SessionStart` hook** → stashes the session id so the command
   can fork the *exact* current session (not "most-recent").

The command degrades gracefully: without the hook, use the commented
`--continue` fallback inside the `.md`.

## 1. Command file

### Method A — symlink (single machine)

```bash
mkdir -p <target-repo>/.claude/commands
ln -s /path/to/ai.skillz/commands/branch-in-new-terminal/branch-in-new-terminal.md \
      <target-repo>/.claude/commands/branch-in-new-terminal.md
```

### Global (available in every project)

```bash
mkdir -p ~/.claude/commands
ln -s /path/to/ai.skillz/commands/branch-in-new-terminal/branch-in-new-terminal.md \
      ~/.claude/commands/branch-in-new-terminal.md
```

Restart Claude Code (commands are discovered at session start).

## 2. `SessionStart` hook (for the precise-id variant)

Merge `session-stash.hook.json` into your `settings.json` — project
(`.claude/settings.json`) or global (`~/.claude/settings.json`). It
runs:

```
jq -r .session_id > "$CLAUDE_PROJECT_DIR/.claude/.current_session"
```

on every session start/resume. Requires `jq`. `$CLAUDE_PROJECT_DIR`
is set for hook commands so it's cwd-robust.

> If you already have a `SessionStart` array, append the inner hook
> object rather than overwriting.

## 3. gitignore the stash file

`.claude/.current_session` is per-machine session state — never
commit it:

```bash
echo '.claude/.current_session' >> <target-repo>/.gitignore
```

## 4. terminal emulator

The spawn line uses `${TERMINAL:-alacritty}` with the `-e` exec flag
(correct for alacritty / xterm / foot). For `gnome-terminal` use
`-- `; for `kitty` pass the command bare — edit the `.md` spawn line
(and `allowed-tools`) accordingly.

## Verify

```
/branch-in-new-terminal
```

A new terminal should open running a forked copy of the session. If
nothing opens, the `SessionStart` hook is probably not installed (the
precise variant reads `.claude/.current_session`).

## TODO

- teach `scripts/deploy-skill.sh` about a `commands/` deploy mode so
  `deploy-skill.sh branch-in-new-terminal <repo>` symlinks the `.md`
  + offers to merge the hook (currently manual, per above).
