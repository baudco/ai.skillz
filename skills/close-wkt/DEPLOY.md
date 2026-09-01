# Deploying `/close-wkt`

The skill source is provider-neutral and shares `/open-wkt`'s existing
`.claude/wkts/` runtime state.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use the portable method: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh close-wkt <repo> \
  --provider <claude|opencode|all>
```

Provider links are created at `.claude/skills/close-wkt` and
`.opencode/skills/close-wkt`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through a version-pinned
`.ai/ai.skillz` anchor.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Without `--stage`, deployment does not stage files. It
does not alter existing worktree state. Quit and restart OpenCode after
deployment or update;
default discovery requires no `opencode.json` or `opencode.jsonc`
mutation.

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review the dry run before migration. Migration preserves
`.claude/wkts/` and `claude_wkts`. `update` advances a submodule anchor;
update a local checkout directly.

## Prerequisites

- `git` CLI

## Companion skill

Deploy `/open-wkt` alongside this skill — they form
a lifecycle pair.
