# Deploying `/py-codestyle`

This whole-directory skill is auto-applied when writing or editing
Python. It has no per-repo state or customization.

## Deployment

Initialize the provider-neutral `.ai/ai.skillz` anchor using an ignored
local checkout link or a portable, version-pinned submodule:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh py-codestyle <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/py-codestyle` and
`.opencode/skills/py-codestyle`. Both are relative whole-directory links
to `.ai/ai.skillz/skills/py-codestyle`.

Track the provider links. With `--method submodule`, also track
`.gitmodules` and the `.ai/ai.skillz` gitlink. With `--method symlink`,
the absolute anchor is ignored. Nothing is staged unless `--stage` is
explicitly supplied.

Quit and restart OpenCode after deployment or update. Its default
`.opencode/skills/` discovery requires no `opencode.json` or
`opencode.jsonc` mutation.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Use `update` for a submodule anchor; update a local source checkout
directly. Review `migrate --dry-run` before applying a legacy migration.

## Prerequisites

None.
