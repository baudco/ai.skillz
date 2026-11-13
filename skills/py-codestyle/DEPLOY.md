# Deploying `/py-codestyle`

This whole-directory skill is intended for every Python/Xonsh
writing task. It has no per-repo state or customization.

## Deployment

Initialize the provider-neutral `.ai/ai.skillz` anchor using an ignored
local checkout link or a portable, version-pinned submodule:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh py-codestyle <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/py-codestyle` and
`.opencode/skills/py-codestyle`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the `.ai/ai.skillz` gitlink only with
`--method submodule`. Local provider links remain ignored. Nothing is staged
unless `--stage` is explicitly supplied.

Quit and restart OpenCode after deployment or update. Its default
`.opencode/skills/` discovery requires no `opencode.json` or
`opencode.jsonc` mutation.

## Agent activation

Keep the skill available for automatic selection. Do not set
`disable-model-invocation: true`: Pi hides such skills from automatic
model selection even when their descriptions say they auto-apply.
Discovery advertises a description, not the complete instructions.

In the consumer's agent entry instructions, require every Python
writer to load the selected skill before editing. For example:

> Before writing, editing or proposing Python/Xonsh code, read the
> project-selected `py-codestyle` skill in full and follow its
> authoring and handoff gate, including helpers, tests, comments and
> docstrings. Formatter/linter success does not replace source review.

Keep policy in the skill; the entry instruction only ensures it is
loaded. An unavailable or divergent deployment must be reported,
not replaced silently with another version. Reload/restart the
consumer after an approved source/deployment update as its harness
requires. These instructions do not install a blocking checker or
guarantee compliance in agents that do not load the skill; enforce
machine-checkable rules in the consumer's supported CI when needed.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Use `update` for a submodule anchor; update a local source checkout
directly. Review `migrate --dry-run` before applying a legacy migration.

## Prerequisites

None.
