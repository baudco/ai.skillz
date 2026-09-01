# Deploying `/inter-skill-review`

This generic whole-directory skill self-triggers after skill changes and
has no per-repo state.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use the portable method: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh inter-skill-review <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/inter-skill-review` and
`.opencode/skills/inter-skill-review`. Local mode uses ignored absolute
links; submodule mode uses trackable relative links through a version-pinned
`.ai/ai.skillz` anchor.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Nothing is staged unless `--stage` is explicitly
supplied. Quit and restart OpenCode after deployment or update. No
`opencode.json` or
`opencode.jsonc` mutation is needed or performed.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Use the dry run before migrating legacy links. `update` applies to a
submodule anchor; update a local checkout directly.

## Prerequisites

Repository file access. The audit phase is read-only;
the approved-change phase may edit skill files after
explicit user sign-off.
