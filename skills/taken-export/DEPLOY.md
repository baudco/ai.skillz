# Deploying `taken-export`

`taken-export` is a generic whole-directory skill with no generated
runtime state inside its skill directory.

## Deployment Script

For the existing Claude-compatible deployment:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh taken-export /path/to/repo
```

This links the canonical directory into:

```text
<repo>/.claude/skills/taken-export
```

## OpenCode

Until provider-aware deployment lands, link the canonical directory into
OpenCode's project discovery tree:

```sh
mkdir -p /path/to/repo/.opencode/skills
ln -s /path/to/ai.skillz/skills/taken-export \
  /path/to/repo/.opencode/skills/taken-export
```

Keep absolute development links untracked. Portable consumers should use
the repository's `ai.skillz` submodule/anchor and a relative link.

Restart OpenCode after deploying or updating the skill; skills are
loaded at session startup.

## Optional Dependencies

- `git` records source repository identity.
- `gish` or forge CLIs provide PR, issue, review, and duplicate context.
- `tkn` validates a target corpus after explicitly authorized apply.
- A task-state ownership skill reinforces the mandatory human authority
  boundary.

The skill still supports chat-only copy/paste handoffs when none of these
optional tools are installed.

## Export Directory

The default artifact location is worktree-local:

```text
.ai/taken/exports/
```

Decide per repository whether exports are ephemeral, ignored, or durable.
Deployment does not add ignore rules and the skill does not stage exports.
