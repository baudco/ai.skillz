# Deploying `/pr-msg`

## Quick setup

```bash
mkdir -p .claude/skills/pr-msg/msgs
ln -s /path/to/ai.skillz/skills/pr-msg/SKILL.md \
      .claude/skills/pr-msg/SKILL.md
ln -s /path/to/ai.skillz/skills/pr-msg/references \
      .claude/skills/pr-msg/references
```

## What stays local (per-repo)

- `msgs/` — generated PR description archive
- `pr_msg_LATEST.md` — most recent PR description

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition
- `references/format-reference.md` — PR format spec

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for PR submission)
