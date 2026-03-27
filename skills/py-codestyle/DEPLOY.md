# Deploying `/py-codestyle`

This skill is fully generic — auto-applied when writing
or editing Python code. No per-repo customization needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/py-codestyle \
      .claude/skills/py-codestyle
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh py-codestyle <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh py-codestyle <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/py-codestyle` → relative symlink
  to `../ai.skillz/skills/py-codestyle`

## Prerequisites

None.
