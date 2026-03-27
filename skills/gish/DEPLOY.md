# Deploying `/gish`

## Quick setup

```bash
ln -s /path/to/ai.skillz/skills/gish \
      .claude/skills/gish
```

This skill is fully generic — no per-repo customization
needed.

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
