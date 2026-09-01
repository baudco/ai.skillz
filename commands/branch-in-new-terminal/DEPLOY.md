# Deploying `/branch-in-new-terminal`

A Claude Code-only slash command that forks the current
conversation (`claude --resume <id> --fork-session`) and opens the
branch in a new terminal window. Unlike skills, commands deploy as a
flat `.md` file under `.claude/commands/`.

Two pieces:
1. the **command** file → `.claude/commands/branch-in-new-terminal.md`
2. a **`SessionStart` hook** → stashes the session id so the command
   can fork the *exact* current session (not "most-recent").

The command degrades gracefully: without the hook, use the commented
`--continue` fallback inside the `.md`.

## 1. Source anchor and command file

Initialize the provider-neutral source anchor once per target repo:

```bash
# Local development: ignored .ai/ai.skillz symlink.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

# Or portable, version-pinned deployment:
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule
```

Deploy the command to its supported provider:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command \
  branch-in-new-terminal <repo> --provider claude
```

Local deployment creates an ignored absolute
`.claude/commands/branch-in-new-terminal.md` link. Submodule deployment
creates a trackable relative link through `.ai/ai.skillz`; track that link,
`.gitmodules`, and the anchor gitlink. The script does not stage files unless
`--stage` is explicitly supplied.

There is no OpenCode implementation of this Claude session-forking
command. Do not deploy it with `--provider opencode`. Restart Claude
Code after deployment because commands are discovered at session start.

For a global Claude-only installation, no repo anchor is required:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command \
  branch-in-new-terminal --global --provider claude
```

Global command deployment does not accept a target repo or `--stage`.

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

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

`migrate` normalizes legacy source links to ignored absolute links for a
local checkout or anchor-relative links for a submodule, while leaving the
manual hook configuration and per-machine session stash intact.
`update` advances a submodule anchor; update a local source checkout
directly. These commands do not edit OpenCode configuration.
The validator checks status, committed absolute provider links, and the
Git index for runtime state such as `.claude/.current_session`.
