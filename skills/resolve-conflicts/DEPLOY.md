# Deploying `/resolve-conflicts`

This skill is fully generic — no per-repo customization
needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/resolve-conflicts \
      .claude/skills/resolve-conflicts
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh resolve-conflicts <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh resolve-conflicts <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/resolve-conflicts` → relative symlink
  to `../ai.skillz/skills/resolve-conflicts`

## Prerequisites

- `git` CLI
