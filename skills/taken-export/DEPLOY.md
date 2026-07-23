# Deploying `taken-export`

`taken-export` is a generic whole-directory skill with no generated
runtime state inside its skill directory.

## Deployment

```bash
# Local: .ai/ai.skillz is an ignored link to a developer checkout.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Portable: .ai/ai.skillz is a version-pinned submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh taken-export <repo> \
  --provider <claude|opencode|all>
```

Provider destinations are `.claude/skills/taken-export` and
`.opencode/skills/taken-export`. Both are relative whole-directory links
through the provider-neutral `.ai/ai.skillz` anchor.

Track provider links. In submodule mode, also track `.gitmodules` and
the anchor gitlink. In local mode, the absolute anchor stays ignored.
Nothing is staged unless `--stage` is explicitly supplied.

Quit and restart OpenCode after deploying or updating the skill. It
uses default `.opencode/skills/` discovery; deployment does not mutate
`opencode.json` or `opencode.jsonc`.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review migration output before applying it. `update` advances a
submodule anchor; local anchors follow their source checkout.

## Optional Dependencies

- `git` records source repository identity.
- `gish` or forge CLIs provide PR, issue, review, and duplicate context.
- `tkn` validates a target corpus after explicitly authorized apply.
- A task-state ownership skill reinforces the mandatory human authority
  boundary.

The skill still supports chat-only copy/paste handoffs when none of these
optional tools are installed.

## Export Directory

The default artifact location is worktree-local:

```text
.ai/taken/exports/
```

Decide per repository whether exports are ephemeral, ignored, or durable.
Deployment does not add ignore rules and the skill does not stage exports.
