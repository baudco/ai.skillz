# Deploying `/open-wkt`

The canonical skill and its root-level `wkts/` runtime layout are
provider-neutral.

## Deployment

```bash
# Ignored local source anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Or portable, version-pinned source anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh open-wkt <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/open-wkt` and
`.opencode/skills/open-wkt`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Local provider links remain ignored. The script stages only when
`--stage` is explicitly supplied. Quit and
restart OpenCode after deployment or update; no `opencode.json` or
`opencode.jsonc` mutation is required or performed.

### What gets gitignored

- `/wkts/`

## Post-deploy setup

### Ensure .gitignore entries

Add to the target repo's `.gitignore`:

```
/wkts/
```

## What stays local (per-repo)

- `wkts/` — linked worktree checkouts
- each linked worktree's private Git directory — lifecycle metadata
- the common Git directory — short-lived ownership guards

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

Source deployment and migration preserve `wkts/` and never place the
worktree root beneath a harness-specific directory.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Preview migration before applying it. `update` advances a submodule;
local anchors follow updates to their source checkout.

## Prerequisites

- `git` CLI
- Optional: `uv` (for `--fixturize` venv creation)

## Companion skill

Deploy `/close-wkt` alongside this skill — they form
a lifecycle pair.
