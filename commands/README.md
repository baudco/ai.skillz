# `ai.skillz/commands`

Reusable Claude Code **slash commands** (the `/name` kind defined by
`.claude/commands/<name>.md`), packaged here like `skills/` so they
can be deployed across repos.

Unlike skills (which deploy as `.claude/skills/<name>/` directories),
a command deploys as a single flat `.md` file under
`.claude/commands/`. Each command lives in its own subdir here with
its docs + any companion config (hooks, etc.):

```
commands/<name>/
  <name>.md                 # the command (symlink → .claude/commands/<name>.md)
  DEPLOY.md                 # symlink + any hook/gitignore setup
  README.md                 # design/reference notes
  *.hook.json               # optional companion SessionStart/… hook snippet
```

## Commands

| Command | Description |
|---------|-------------|
| `branch-in-new-terminal` | Fork the current session and open the branch in a new terminal window (precise-id via `SessionStart` hook, or `--continue` fallback). |

## Deployment

`deploy.sh` has a first-class `command` mode:

```bash
deploy.sh command <name> <target-repo>   # symlink into .claude/commands/
deploy.sh command <name> --global        # into ~/.claude/commands/
deploy.sh command all   <target-repo>     # every command
```

It symlinks the `.md` (absolute, or submodule-relative when the repo
has the `.claude/ai.skillz` submodule), merges the command's
`.gitignore` patterns (from `gitignore-patterns.conf`), and prints any
companion-hook merge hint. Per-command `DEPLOY.md` covers the rest
(hook install into `settings.json`).

> Note: `claude-reply` is a Neovim plugin, **not** a slash-command, so
> `deploy.sh command` does not apply to it — see its `DEPLOY.md`.
