# Deploying `/open-wkt`

The canonical skill is provider-neutral, but its established worktree
runtime layout remains under `.claude/`.

## Deployment

```bash
# Ignored local source anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Or portable, version-pinned source anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh open-wkt <repo> \
  --provider <claude|opencode|all>
```

`.ai/ai.skillz` is the shared source anchor. The provider destinations
are `.claude/skills/open-wkt` and `.opencode/skills/open-wkt`, linked
relatively to the same canonical skill.

Track provider links. In submodule mode, also track `.gitmodules` and
the anchor gitlink; in local mode, ignore the absolute anchor. The
script stages only when `--stage` is explicitly supplied. Quit and
restart OpenCode after deployment or update; no `opencode.json` or
`opencode.jsonc` mutation is required or performed.

### What gets gitignored

- `.claude/wkts/`, `claude_wkts`

## Post-deploy setup

### Ensure .gitignore entries

Add to the target repo's `.gitignore`:

```
.claude/wkts/
claude_wkts
```

## What stays local (per-repo)

- `.claude/wkts/` — worktree instances + metadata
- `claude_wkts` — convenience symlink

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

Source deployment and migration preserve `.claude/wkts/`, its metadata,
and `claude_wkts`; they do not rename this runtime contract for
OpenCode.

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
