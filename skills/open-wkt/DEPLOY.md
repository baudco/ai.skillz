# Deploying `/open-wkt`

## Method A: Absolute symlinks (single machine)

### 1. Create skill directory in your repo

```bash
mkdir -p .claude/skills/open-wkt
```

### 2. Symlink the generic SKILL.md

```bash
ln -s /path/to/ai.skillz/skills/open-wkt/SKILL.md \
      .claude/skills/open-wkt/SKILL.md
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh open-wkt <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh open-wkt <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/open-wkt/SKILL.md` → relative symlink
  to `../../ai.skillz/skills/open-wkt/SKILL.md`

### What gets gitignored

- `.claude/wkts/`, `claude_wkts`

## Post-deploy setup

### Ensure .gitignore entries

Add to the target repo's `.gitignore`:

```
.claude/wkts/
claude_wkts
```

## What stays local (per-repo)

- `.claude/wkts/` — worktree instances + metadata
- `claude_wkts` — convenience symlink

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

## Prerequisites

- `git` CLI
- Optional: `uv` (for `--fixturize` venv creation)

## Companion skill

Deploy `/close-wkt` alongside this skill — they form
a lifecycle pair.
