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

Requires the modden dev environment with `py-gitea`. Configure the launcher
with a durable absolute path to that environment's xonsh:

```bash
/path/to/deployed/gish/scripts/gish-xontrib \
  --configure /path/to/modden/.venv/bin/xonsh
/path/to/deployed/gish/scripts/gish-xontrib --check
```

`--configure` verifies that `xontrib load gish` succeeds under `--no-rc`,
then writes only the absolute interpreter path to
`$XDG_CONFIG_HOME/ai.skillz/gish-xonsh` with mode 0600. The
`AI_SKILLZ_GISH_XONSH` environment variable provides a process-local override.
Re-run the check after rebuilding or moving the modden environment.

OpenCode's top-level `shell` setting is independent. Prefer a stable
profile-installed shell and let this launcher enter the modden environment.
If the user deliberately configures OpenCode itself with the modden venv's
xonsh, use an absolute path and explain that moving, rebuilding, or deleting
that environment will prevent all OpenCode subprocesses from starting. Never
rewrite `opencode.json` or `opencode.jsonc` as an implicit side effect of skill
deployment.

Token location: `~/opsec/gitea/py-gitea.key`
