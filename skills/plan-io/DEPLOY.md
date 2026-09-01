# Deploying `/plan-io`

This generic whole-directory skill writes plans under the
provider-neutral `plans/<ai-service>/` convention.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use a portable, version-pinned anchor: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh plan-io <repo> \
  --provider <claude|opencode|all>
```

Provider links are created at `.claude/skills/plan-io` and/or
`.opencode/skills/plan-io`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

The active provider writes its own plan namespace, such as
`plans/claude/` or `plans/opencode/`. These are project artifacts, not
skill source state. Preserve their contents during migration and keep
their task markers human-owned.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Local provider links remain ignored. Deployment
stages only when `--stage` is explicitly supplied. Quit and restart
OpenCode after deploy or update. Its
default skill discovery needs no `opencode.json` or `opencode.jsonc`
mutation.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review migration output before applying it; migration does not rewrite
historical plans. `update` advances a submodule anchor, while local
anchors follow their source checkout.

## Prerequisites

None. This skill governs file placement conventions
only.
