# Deploying `/commit-msg`

`commit-msg` is hybrid: canonical workflow content is shared, while its
style guide, session configuration, and generated messages remain local
to each consumer repository.

## Deployment

```bash
# Local development anchor (ignored absolute symlink).
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Or portable, version-pinned anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider <claude|opencode|all>
```

The source anchor is always `.ai/ai.skillz`. Deployment creates hybrid
directories at `.claude/skills/commit-msg/` and/or
`.opencode/skills/commit-msg/`, with `SKILL.md` linked relatively to the
same canonical file. It does not replace either directory, so existing
local files survive migration and redeployment.

The workflow's persisted runtime contract remains under `.claude/`:

- `.claude/skills/commit-msg/style-guide-reference.md`
- `.claude/skills/commit-msg/conf.toml`
- `.claude/skills/commit-msg/msgs/`
- `.claude/git_commit_msg_LATEST.md`
- `.claude/review_context.md` and `.claude/review_regression.md`

This state remains local or ignored as appropriate. Source-anchor
migration does not move, delete, or rewrite it.

## OpenCode command

Deploy the reusable OpenCode command shim separately:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider opencode
bash /path/to/ai.skillz/scripts/deploy.sh command commit-msg <repo> \
  --provider opencode
```

The first command is required even if another provider already has the
skill. Command deployment refuses a missing or unhealthy OpenCode skill.

Track `.opencode/commands/commit-msg.md`; consumer deployment copies it
from `.ai/ai.skillz/providers/opencode/commands/commit-msg.md`. This
`ai.skillz` checkout itself uses a tracked relative link to the canonical
provider asset. There is no corresponding Claude command asset to deploy.
OpenCode discovers the command and skill through its default project
directories, so the script does not mutate `opencode.json` or
`opencode.jsonc`. Quit and restart OpenCode after deployment or update.

## Tracking

Track provider source links. In submodule mode, also track
`.gitmodules` and the `.ai/ai.skillz` gitlink. In local mode, ignore the
absolute anchor. Nothing is staged unless `--stage` is explicitly
supplied.

## Post-deploy setup

### Generate a project-specific style guide

**Option A** (recommended): use the
`generate-style-guide.py` script (no deps beyond
Python stdlib):

```bash
python <repo>/.ai/ai.skillz/scripts/generate-style-guide.py \
  <repo> --commits 500 \
  --output .claude/skills/commit-msg/style-guide-reference.md
```

This analyzes the repo's commit history and writes
a complete `style-guide-reference.md` with quantified
patterns (verb frequencies, backtick usage, section
markers, abbreviations, tone indicators, examples).

Optional flags:
- `--author <pattern>` — filter to a specific
  author's commits
- `-n <count>` — number of commits (default: 500)

**Option B**: have the active coding agent analyze your commit
history and write the style guide manually, using
the examples in
`.ai/ai.skillz/skills/commit-msg/references/` as
models. The output should match the same structure
as Option A's generated guide.

### (Optional) Create session tracking config

```bash
cp <repo>/.ai/ai.skillz/templates/commit-msg/conf.toml.j2 \
   .claude/skills/commit-msg/conf.toml
```

Edit to uncomment and set a fresh UUID, or let the
skill generate one on first invocation.

## What stays local (per-repo)

- `style-guide-reference.md` — your repo's commit style
- `conf.toml` — session tracking UUID
- `msgs/` — generated commit message archive

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

`status` reports anchor health, hybrid links, command presence, legacy
layouts, and unportable OpenCode `skills.paths`. Review the migration
dry run before applying it. `update` advances a submodule anchor; update
a local checkout directly.

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for review context integration
  with `/code-review-changes`)
