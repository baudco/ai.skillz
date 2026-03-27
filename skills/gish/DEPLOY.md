# Deploying `/gish`

This skill is fully generic — no per-repo customization
needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/gish \
      .claude/skills/gish
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh gish <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh gish <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/gish` → relative symlink
  to `../ai.skillz/skills/gish`

## Prerequisites

- `git` CLI
- For GitHub: `gh` CLI (authenticated)
- For Gitea: `xonsh` + `py-gitea` (via modden dev env)

## Backend-specific setup

### GitHub

Just ensure `gh auth login` is done. No additional
config needed.

### Gitea

Requires the modden dev environment with `py-gitea`:
```bash
nix develop -c xonsh   # from modden repo
# or
pyup modden; reloadxsh gish
```

Token location: `~/opsec/gitea/py-gitea.key`
