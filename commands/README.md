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
  <name>.xsh                # optional xonsh-alias implementation
  DEPLOY.md                 # symlink + any hook/gitignore/alias setup
  README.md                 # design/reference notes
  *.hook.json               # optional companion SessionStart/… hook snippet
```

## Commands

| Command | Description |
|---------|-------------|
| `branch-in-term` | Fork the current session into a new terminal (modden-aware xonsh alias; precise-id via `SessionStart` hook, or `--continue` fallback). |
| `claude-reply` | **(nvim plugin, not a slash-command)** Reformat Claude Code's Ctrl-G "edit last response" buffer for email-style quote-reply: `]m`/`[m` section nav + `\e` to pull a section down as a `gq`-wrapped `> ` quote. Deploys by symlink into the nvim config (see its `DEPLOY.md`), not via `deploy-skill.sh`. |

## Deployment

`deploy-skill.sh` has a first-class `command` mode:

```bash
deploy-skill.sh command <name> <target-repo>   # symlink into .claude/commands/
deploy-skill.sh command <name> --global        # into ~/.claude/commands/
deploy-skill.sh command all   <target-repo>     # every command
```

It symlinks the `.md` (absolute, or submodule-relative when the repo
has the `.claude/ai.skillz` submodule), merges the command's
`.gitignore` patterns (from `gitignore-patterns.conf`), and prints any
companion-hook merge hint. Per-command `DEPLOY.md` covers the rest
(hook install into `settings.json`, sourcing any `.xsh` alias).
