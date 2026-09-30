# Deploying `/py-codestyle`

This whole-directory skill is auto-applied when writing or editing
Python. Its shared reference covers general review lessons. A
consumer repository may add project-specific runtime and review
lessons at `.ai/py-codestyle/review-lessons.md`. The skill reads
that file from the active worktree when it exists; deployment
does not create or overwrite it. Keep project topology and local
test-case examples there rather than editing the shared skill.

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
`.opencode/skills/py-codestyle`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the `.ai/ai.skillz` gitlink only with
`--method submodule`. Local provider links remain ignored. Nothing is staged
unless `--stage` is explicitly supplied.

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
