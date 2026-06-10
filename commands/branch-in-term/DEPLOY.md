# Deploying `/branch-in-term`

A custom Claude Code **slash command** that forks the current
conversation (`claude --resume <id> --fork-session`) into a new
terminal. It is a **prompt-command**: when invoked it asks Claude to
run the spawn via the **Bash tool** — *not* an inline `!`-exec.

> ## Why not a `!`-exec one-liner?
> A slash-command's inline `` !`cmd` `` runs through Claude Code's
> static command-safety analyzer, which **hard-blocks process
> spawners** (`setsid`, `xonsh -c`, `nohup`, …): *"runs its argument
> as a command — cannot be statically analyzed."* No `allowed-tools`
> entry overrides it. So the spawn has to go through the Bash tool
> (which *can* run `setsid`) or a user-initiated input-box `!`.

Pieces:
1. the **command** file → `.claude/commands/branch-in-term.md`
2. a **`SessionStart` hook** → stashes the exact session id so the
   command forks THIS session (not "most-recent").

## 1. Command file (via the deploy script)

```bash
# into a target repo (auto symlink/submodule method):
bash /path/to/ai.skillz/scripts/deploy-skill.sh command branch-in-term <target-repo>

# or globally, into ~/.claude/commands/ (every project):
bash /path/to/ai.skillz/scripts/deploy-skill.sh command branch-in-term --global

# every command at once:
bash /path/to/ai.skillz/scripts/deploy-skill.sh command all <target-repo>
```

Symlinks `branch-in-term.md` into `.claude/commands/`, merges the
`.claude/.current_session` gitignore pattern, and prints the hook
hint. Restart Claude Code — commands are discovered at session start.

## 2. `SessionStart` hook (explicit session id)

Merge `session-stash.hook.json` into your `settings.json` — project
(`.claude/settings.json`) or global (`~/.claude/settings.json`). It
runs, on every session start/resume:

```
jq -r .session_id > "$CLAUDE_PROJECT_DIR/.claude/.current_session"
```

Requires `jq`. `$CLAUDE_PROJECT_DIR` is cwd-robust. Without it the
command falls back to `--continue` (most-recent in cwd).

> If you already have a `SessionStart` array, append the inner hook
> object rather than overwriting.

`.claude/.current_session` is per-machine state — gitignored
automatically by the deploy script (`[branch-in-term]` in
`gitignore-patterns.conf`).

## Usage + permission note

`/branch-in-term [title]` → Claude runs the `setsid … claude --resume
… --fork-session` spawn via Bash. The Bash tool will likely **prompt
to approve** that spawn each run (`setsid` can't be statically
allow-listed). Approve it.

**Zero-friction alternative** (user-initiated, bypasses the analyzer):
type the spawn directly in the input box with the `!` prefix —

```
! setsid -f alacritty -e claude --resume "$(cat .claude/.current_session)" --fork-session
```

or wrap it in a tiny PATH script and run `! branch-fork [title]`. A
fixed-path wrapper script can also be allow-listed by exact path
(`Bash(/abs/.../branch-fork.sh)`), which makes the `/` command
frictionless — an easy follow-up.

## 3. (Optional, future) modden-aware xonsh alias

`branch-in-term.xsh` is an **experimental** xonsh alias (not wired
into the command). Sourced from your xonshrc it gives WM-aware
placement inside a modden workspace: it reads `$_MODDEN_RT_VARS`
(carries `bigd_alacritty_socket`) and opens the fork as a **sibling
window in the same alacritty tree** via `alacritty msg -s <socket>
create-window` — modden's own sub-terminal mechanism. Outside modden
it spawns a standalone `$TERMINAL -e …`. Revisit when wiring the
slash-command up to it is worth the effort.

```xonsh
source /path/to/ai.skillz/commands/branch-in-term/branch-in-term.xsh
# then: branch-in-term [title]   (at the prompt, or via input-box `!`)
```

## Verify

```
/branch-in-term
```

Claude runs the Bash spawn; approve it; a new terminal opens running a
forked copy of the session. If it forks the wrong session, the
`SessionStart` hook isn't installed (so it used `--continue`).
