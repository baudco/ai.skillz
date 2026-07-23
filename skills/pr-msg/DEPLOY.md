# Deploying `/pr-msg`

`pr-msg` is hybrid: its workflow, references, and scripts are canonical,
while generated PR descriptions remain local to the consumer repo.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use a portable, version-pinned anchor: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh pr-msg <repo> \
  --provider <claude|opencode|all>
```

Both methods use the provider-neutral `.ai/ai.skillz` source anchor.
Deployment creates `.claude/skills/pr-msg/` and/or
`.opencode/skills/pr-msg/` as local hybrid directories. `SKILL.md`,
`references/`, and `scripts/` are relative links through the anchor;
the directories themselves are not replaced.

The existing persisted runtime contract remains under
`.claude/skills/pr-msg/`, including `msgs/` and `pr_msg_LATEST.md`.
These generated files stay local and ignored. Migration preserves them
byte-for-byte rather than moving them into `.ai` or `.opencode`.

Track the canonical provider links. Submodule mode also tracks
`.gitmodules` and the `.ai/ai.skillz` gitlink; local mode ignores the
absolute anchor. Nothing is staged unless `--stage` is explicitly
supplied.

Quit and restart OpenCode after deployment or update. Default
`.opencode/skills/` discovery needs no `opencode.json` or
`opencode.jsonc` mutation.

## What stays local (per-repo)

- `msgs/` — generated PR description archive
- `pr_msg_LATEST.md` — most recent PR description

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition
- `references/format-reference.md` — PR format spec
- `scripts/rewrap.py` — line-width enforcement tool

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review the dry run before migrating legacy absolute or
`.claude/ai.skillz` links. `update` advances a submodule anchor; local
anchors follow their source checkout.

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for PR submission)
