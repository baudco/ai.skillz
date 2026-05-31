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

Per-command `DEPLOY.md` covers the steps. In short: symlink the `.md`
into a target repo's `.claude/commands/` (or `~/.claude/commands/` for
global), then install any companion hook into `settings.json`.

> TODO: extend `scripts/deploy-skill.sh` with a `commands/` mode so
> commands deploy with the same symlink/submodule ergonomics as
> skills (currently the `.md` symlink + hook merge is manual).
