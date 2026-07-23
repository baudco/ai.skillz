# Deploying `/dep-supersede-scan`

This generic whole-directory skill reads the branch diff and queries
GitHub's Dependabot API. It has no per-repo skill state.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use a portable anchor: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh dep-supersede-scan <repo> \
  --provider <claude|opencode|all>
```

The provider-neutral source anchor is `.ai/ai.skillz`. Local mode uses
an ignored absolute anchor symlink; submodule mode uses a tracked,
version-pinned anchor. Relative provider links are created at
`.claude/skills/dep-supersede-scan` and
`.opencode/skills/dep-supersede-scan`.

Track provider links and the submodule artifacts when applicable. The
script stages only when `--stage` is explicitly supplied. Quit and
restart OpenCode after deployment or update; no `opencode.json` or
`opencode.jsonc` edit is performed.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review dry-run output before migration. `update` advances a submodule;
local anchors follow updates to their source checkout.

## Prerequisites

- `gh` CLI authenticated with `security_events` read
  scope (for the dependabot alerts API). Without it the
  alert pass is skipped (reported, not silent); the
  bot-PR pass still works.
- `git` CLI.
- Optional: `python` with `packaging` for PEP-440 version
  comparison (falls back to manual review when absent).

## Pairs with

- `/pr-msg` — findings feed its "Related issues & PRs" /
  Links pass.
