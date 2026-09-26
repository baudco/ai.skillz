# Deploying `/prompt-io`

The skill source is a generic whole directory. New prompt records
are durable, provider-neutral project artifacts directly under
`ai/prompt-io/`.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh prompt-io <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Shared deployment (`agents` or its `codex` alias) creates a whole
directory link at `.agents/skills/prompt-io`. Legacy selectors use
`.claude/skills/prompt-io` and/or `.opencode/skills/prompt-io`;
`all` retains its Claude plus OpenCode meaning. `--provider` remains
an alias for `--harness`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.
The active harness identifies itself in record front matter, not
in the directory name.

Always track the durable prompt records required by project policy. Track
provider links, `.gitmodules`, and the anchor gitlink only in submodule mode;
local provider links remain ignored. Deployment does
not modify existing prompt logs and stages only when `--stage` is
explicitly supplied.

Quit and restart OpenCode after deployment or update. Default
`.opencode/skills/` discovery needs no `opencode.json` or
`opencode.jsonc` mutation.

## Tracked prompt records

- `ai/prompt-io/README.md`
- `ai/prompt-io/<timestamp>_<identifier>.md`
- `ai/prompt-io/<timestamp>_<identifier>.raw.md`

Historical `ai/prompt-io/<service>/` records and their existing
`Prompt-IO:` paths remain valid. Source migration preserves them
in place. Both layouts are discoverable; commit trailers name only
the structured log, never its `.raw.md` partner.

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
