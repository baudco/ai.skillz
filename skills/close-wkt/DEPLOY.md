# Deploying `/close-wkt`

## Method A: Absolute symlinks (single machine)

### 1. Create skill directory in your repo

```bash
mkdir -p .claude/skills/close-wkt
```

### 2. Symlink the generic SKILL.md

```bash
ln -s /path/to/ai.skillz/skills/close-wkt/SKILL.md \
      .claude/skills/close-wkt/SKILL.md
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh close-wkt <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh close-wkt <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/close-wkt/SKILL.md` → relative symlink
  to `../../ai.skillz/skills/close-wkt/SKILL.md`

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

## Prerequisites

- `git` CLI

## Companion skill

Deploy `/open-wkt` alongside this skill — they form
a lifecycle pair.
