# Deploying `/git-mgmt`

This is a generic whole-directory skill with no per-repository state.

## Deployment

```bash
# Local anchor: ignored .ai/ai.skillz symlink to this checkout.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Portable anchor: version-pinned .ai/ai.skillz submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh git-mgmt <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/git-mgmt` and
`.opencode/skills/git-mgmt`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Local provider links remain ignored, and deployment stages only when
`--stage` is explicitly supplied. Quit and restart OpenCode after deployment
or update because skill discovery occurs at startup.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

## Prerequisites

- `git` CLI
- Deployed `resolve-conflicts` companion for authorized conflict resolution
- Optional deployed `gish` skill for provider-neutral forge inspection

Fresh forge inspection additionally requires an adapter supported by `gish`,
an authenticated provider client, and explicit current-prompt network
authorization. Without those capabilities, `/git-mgmt` is limited to clearly
labeled local/prospective inspection.

For the current modden-backed Gitea adapter, deploy `gish` beside this skill
and configure its runtime explicitly:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh gish <repo> \
  --provider <claude|opencode|all>
<provider-root>/skills/gish/scripts/gish-xontrib \
  --configure /absolute/path/to/modden-venv/bin/xonsh
<provider-root>/skills/gish/scripts/gish-xontrib --check
```

The runtime selection is user-level and shared by downstream repositories; it
is not repository deployment state. `git-mgmt` remains usable without it:

- use an explicitly authorized direct provider query when it returns the full
  required identity record;
- otherwise continue with clearly labeled local/prospective Git inspection.

## OpenCode shell

OpenCode's top-level `shell` setting controls every subprocess, not only
`gish`. Skill deployment therefore never writes it. Configure an absolute
path in the user's global `opencode.json` when desired:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "shell": "/absolute/path/to/xonsh"
}
```

The recommended setup uses a stable profile shell here and lets
`gish-xontrib` select the modden environment. A user may instead select the
modden venv's xonsh, but must accept that moving, rebuilding, or deleting that
environment prevents all OpenCode commands from starting. Confirm the path is
executable, inspect `opencode debug config`, and restart OpenCode because its
configuration is loaded at startup.

The canonical provider overlays currently support Claude Code and OpenCode.
Other agentskills.io consumers may read the provider-neutral workflow, but
must supply equivalent Git, local-read, and separately authorized forge
capabilities; the frontmatter tool grants are not portable permission policy.
