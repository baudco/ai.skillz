# Deploying `/resolve-conflicts`

This is a generic whole-directory skill with no per-repo state.

## Deployment

```bash
# Local anchor: ignored .ai/ai.skillz symlink to this checkout.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Portable anchor: version-pinned .ai/ai.skillz submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh resolve-conflicts <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/resolve-conflicts` and
`.opencode/skills/resolve-conflicts`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Local provider links remain ignored, and deployment stages only when
`--stage` is explicitly supplied. Quit and restart OpenCode
after deployment or update.
Default `.opencode/skills/` discovery needs no `opencode.json` or
`opencode.jsonc` mutation.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Preview migration before replacing legacy links. `update` advances a
submodule anchor; local anchors follow their source checkout.

## Prerequisites

- `git` CLI
