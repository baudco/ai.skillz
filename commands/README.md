# `ai.skillz/commands`

Reusable slash commands are provider-specific adapters around canonical
skills or provider workflows. Commands deploy as flat Markdown files in
the selected provider's default discovery directory:

- Claude Code: `.claude/commands/<name>.md`
- OpenCode: `.opencode/commands/<name>.md`

Claude command packages live here with their docs and companion config:

```
commands/<name>/
  <name>.md                 # the command (symlink → .claude/commands/<name>.md)
  DEPLOY.md                 # symlink + any hook/gitignore setup
  README.md                 # design/reference notes
  *.hook.json               # optional companion SessionStart/… hook snippet
```

## Commands

| Command | Provider | Description |
|---------|----------|-------------|
| `branch-in-new-terminal` | Claude Code | Fork the current session and open the branch in a new terminal window (precise-id via `SessionStart` hook, or `--continue` fallback). |
| `commit-msg` | OpenCode | Load the canonical `commit-msg` skill for staged changes. |
| `run-tests` | OpenCode | Load the canonical test workflow and repository harness. |
| `taken-export` | OpenCode | Export repository work as Taken-compatible Org tasks. |

Reusable OpenCode shims are stored at
`providers/opencode/commands/<name>.md`; this checkout's matching
`.opencode/commands/<name>.md` paths are relative links to them.

## Deployment

Initialize the provider-neutral `.ai/ai.skillz` anchor using either the
local symlink or portable submodule method, then deploy only commands
implemented for the selected provider:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh command \
  branch-in-new-terminal <repo> --provider claude

# Required before the OpenCode command can be installed:
bash /path/to/ai.skillz/scripts/deploy.sh \
  commit-msg <repo> --provider opencode
bash /path/to/ai.skillz/scripts/deploy.sh command \
  commit-msg <repo> --provider opencode

# Claude commands may instead be installed globally; OpenCode commands
# remain repository-local.
bash /path/to/ai.skillz/scripts/deploy.sh command \
  branch-in-new-terminal --global --provider claude
```

The deploy script refuses the OpenCode command unless the associated
`.opencode/skills/commit-msg` deployment is healthy.

Local command deployment uses ignored absolute links. Submodule deployment
uses trackable relative links through `.ai/ai.skillz`; also track
`.gitmodules` and the anchor gitlink. Nothing is staged unless `--stage` is
explicitly supplied.

`--provider claude|opencode|all` selects provider destinations, but a
command is deployed only where an implementation exists. The Claude
`branch-in-new-terminal` command also merges its `.gitignore` pattern
and prints the manual `SessionStart` hook instructions.

Skill and command deployment defaults to Claude, while status defaults
to both providers. Global deployment is Claude-only, does not accept a
target repo or `--stage`, and uses local symlinks rather than an anchor.

OpenCode's default `.opencode/commands/` discovery needs no
`opencode.json` or `opencode.jsonc` mutation. Quit and restart OpenCode
after command deployment or update. Use
`deploy.sh status <repo> --provider all` to inspect command links,
preview legacy movement with
`deploy.sh migrate <repo> --dry-run`, and advance a submodule anchor with
`deploy.sh update <repo>`. Run `scripts/validate-deployment.sh <repo>`
afterward to check status, manifest dependencies, committed absolute
links, and tracked or staged runtime state in the Git index.

> Note: `claude-reply` is a Neovim plugin, **not** a slash-command, so
> `deploy.sh command` does not apply to it. See the standalone
> [`ai.reply` deployment guide][ai-reply-deploy] or the local checkout
> at `~/repos/ai.reply/DEPLOY.md`.

[ai-reply-deploy]: https://github.com/baudco/ai.reply/blob/main/DEPLOY.md
