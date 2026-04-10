# Deploying `/pr-msg`

## Method A: Absolute symlinks (single machine)

```bash
mkdir -p .claude/skills/pr-msg/msgs
ln -s /path/to/ai.skillz/skills/pr-msg/SKILL.md \
      .claude/skills/pr-msg/SKILL.md
ln -s /path/to/ai.skillz/skills/pr-msg/references \
      .claude/skills/pr-msg/references
ln -s /path/to/ai.skillz/skills/pr-msg/scripts \
      .claude/skills/pr-msg/scripts
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh pr-msg <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh pr-msg <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/pr-msg/SKILL.md` → relative symlink
  to `../../ai.skillz/skills/pr-msg/SKILL.md`
- `.claude/skills/pr-msg/references` → relative symlink
  to `../../ai.skillz/skills/pr-msg/references`
- `.claude/skills/pr-msg/scripts` → relative symlink
  to `../../ai.skillz/skills/pr-msg/scripts`

### What gets gitignored

- `msgs/`, `pr_msg_LATEST.md`

## What stays local (per-repo)

- `msgs/` — generated PR description archive
- `pr_msg_LATEST.md` — most recent PR description

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition
- `references/format-reference.md` — PR format spec
- `scripts/rewrap.py` — line-width enforcement tool

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for PR submission)
