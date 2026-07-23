# Deploying `/gish`

This is a generic whole-directory skill with backend-specific external
prerequisites but no per-repo skill state.

## Deployment

```bash
# Local checkout anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Or portable, version-pinned anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh gish <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/gish` and
`.opencode/skills/gish`. Local mode uses ignored absolute links; submodule
mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the anchor gitlink only for
submodule deployments. Local provider links remain ignored.
The script stages only when `--stage` is explicitly supplied. Quit and
restart OpenCode after deploy or update. It uses default discovery and
does not mutate `opencode.json` or `opencode.jsonc`.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review migration output before applying it. `update` advances only a
submodule anchor; update a local checkout with its normal Git workflow.

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
