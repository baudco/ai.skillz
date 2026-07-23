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

The local method makes `.ai/ai.skillz` an ignored absolute symlink; the
submodule method makes it a tracked, version-pinned source anchor. The
provider destinations are `.claude/skills/inter-skill-review` and
`.opencode/skills/inter-skill-review`, each linked relatively through
the provider-neutral anchor.

Track provider links and, for submodule mode, `.gitmodules` plus the
anchor gitlink. Nothing is staged unless `--stage` is explicitly
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

None (reads skill files only).
