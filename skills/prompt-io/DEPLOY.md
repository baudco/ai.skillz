# Deploying `/prompt-io`

The skill source is a generic whole directory. Prompt records are
provider-neutral project artifacts namespaced by AI service.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh prompt-io <repo> \
  --provider <claude|opencode|all>
```

The source anchor is `.ai/ai.skillz`. Relative provider links are
created at `.claude/skills/prompt-io` and/or
`.opencode/skills/prompt-io`. The active service writes under
`ai/prompt-io/claude/`, `ai/prompt-io/opencode/`, or another matching
service namespace.

Track provider links and the durable prompt records required by project
policy. With submodule mode, also track `.gitmodules` and the anchor
gitlink; with local mode, ignore the absolute anchor. Deployment does
not modify existing prompt logs and stages only when `--stage` is
explicitly supplied.

Quit and restart OpenCode after deployment or update. Default
`.opencode/skills/` discovery needs no `opencode.json` or
`opencode.jsonc` mutation.

## Tracked prompt records

- `ai/prompt-io/<service>/README.md`
- `ai/prompt-io/<service>/*_prompt_io.md`
- `ai/prompt-io/<service>/*_prompt_io.raw.md`

Source migration preserves these records in place.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Review the dry run before migration. `update` advances a submodule
anchor; update a local source checkout directly.

## NLNet compliance

This skill implements logging required by:
https://nlnet.nl/foundation/policies/generativeAI/

Deploy it in any NLNet-funded project to ensure
prompt provenance tracking.

## Prerequisites

- `git` CLI
- An AI coding agent that supports the
  agentskills.io specification
