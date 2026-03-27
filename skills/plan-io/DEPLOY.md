# Deploying `/plan-io`

This skill is fully generic — no per-repo customization
needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/plan-io \
      .claude/skills/plan-io
mkdir -p plans/claude
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh plan-io <your-repo>
mkdir -p <your-repo>/plans/claude
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh plan-io <your-repo>
mkdir -p <your-repo>/plans/claude
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/plan-io` → relative symlink
  to `../ai.skillz/skills/plan-io`

## Prerequisites

None. This skill governs file placement conventions
only.
