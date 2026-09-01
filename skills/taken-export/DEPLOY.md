# Deploying `taken-export`

`taken-export` is a generic whole-directory skill with no generated
runtime state inside its skill directory.

## Deployment

```bash
# Local: provider links point directly to this checkout and stay ignored.
bash /path/to/ai.skillz/scripts/deploy.sh taken-export <repo> \
  --provider <claude|opencode|all> --method symlink

# Portable: initialize a version-pinned anchor and use relative links.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule
bash /path/to/ai.skillz/scripts/deploy.sh taken-export <repo> \
  --provider <claude|opencode|all> --method submodule
```

Provider destinations are `.claude/skills/taken-export` and
`.opencode/skills/taken-export`. Local mode creates ignored absolute links;
portable mode creates trackable relative links through `.ai/ai.skillz`.

OpenCode also needs its command shim:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command taken-export <repo> \
  --provider opencode --method symlink
# Use --method submodule after portable initialization.
```

The canonical shim is tracked at
`providers/opencode/commands/taken-export.md`. Local provider links stay
ignored. In submodule mode, track the relative links, `.gitmodules`, and the
anchor gitlink. Nothing is staged unless `--stage` is explicitly supplied.

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

Deployment ignores this directory by default. Remove that pattern only when
exports are intentionally durable repository artifacts. The skill itself
does not stage exports or change ignore policy during an export.
