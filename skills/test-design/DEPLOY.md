# Deploying `/test-design`

`test-design` is a generic whole-directory skill with no repository-local
runtime state or override. It requires the canonical `run-tests` skill so all
concrete test execution remains owned by one workflow.

## Deployment

Deploy ignored local links:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --provider <claude|opencode|all> --method symlink
bash /path/to/ai.skillz/scripts/deploy.sh test-design <repo> \
  --provider <claude|opencode|all> --method symlink
```

Deployment stops when `run-tests` is missing or unhealthy for the selected
provider. `run-tests` remains independently deployable and does not require
`test-design`.

For a portable deployment:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --provider <claude|opencode|all> --method submodule
bash /path/to/ai.skillz/scripts/deploy.sh test-design <repo> \
  --provider <claude|opencode|all> --method submodule
```

Local mode creates ignored absolute links. Submodule mode creates trackable
relative links through `.ai/ai.skillz`. Nothing is staged unless `--stage` is
explicitly supplied, and deployment never commits.

## OpenCode

OpenCode skill deployment installs the dependent `/test-design` command shim
automatically. No `opencode.json` mutation is required:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh test-design <repo> \
  --provider opencode --method symlink
```

The canonical shim is
`providers/opencode/commands/test-design.md`. Restart OpenCode after deployment
because skills and commands load at process startup.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

An absolute link may need deployment in each worktree. A tracked relative
submodule link is portable when the submodule is initialized there.
