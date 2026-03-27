# Deploying `/inter-skill-review`

This skill is fully generic — no per-repo customization
needed. It self-triggers after any skill modification.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/inter-skill-review \
      .claude/skills/inter-skill-review
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh inter-skill-review <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh inter-skill-review <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/inter-skill-review` → relative symlink
  to `../ai.skillz/skills/inter-skill-review`

## Prerequisites

None (reads skill files only).
