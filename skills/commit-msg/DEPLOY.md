# Deploying `/commit-msg`

`commit-msg` is hybrid: canonical workflow content is shared, while its
style guide and generated messages remain local
to each consumer repository.

## Deployment

```bash
# Local development anchor (ignored absolute symlink).
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Or portable, version-pinned anchor.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh resolve-conflicts <repo> \
  --provider <claude|opencode|all>
bash /path/to/ai.skillz/scripts/deploy.sh git-mgmt <repo> \
  --provider <claude|opencode|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider <claude|opencode|all>
```

Deployment creates hybrid directories at `.claude/skills/commit-msg/` and/or
`.opencode/skills/commit-msg/`. Local mode uses ignored absolute `SKILL.md`
links; submodule mode uses trackable relative links through `.ai/ai.skillz`.
It does not replace either directory, so existing local files survive
migration and redeployment.

`commit-msg` requires `git-mgmt` for its local existing-work commit-time
backstop. Deployment stops rather than generating commit guidance without the
gate; the manifest also installs `git-mgmt`'s `resolve-conflicts` dependency.

The workflow's persisted runtime contract remains under `.claude/`:

- `.claude/skills/commit-msg/style-guide-reference.md`
- `.claude/skills/commit-msg/msgs/`
- `.claude/git_commit_msg_LATEST.md`
- `.claude/review_context.md`, `.claude/review_regression.md`, and
  `.claude/review_replies/`

This state remains local or ignored as appropriate. Source-anchor
migration does not move, delete, or rewrite it.

## OpenCode command

OpenCode skill deployment installs the reusable command shim automatically.
The explicit command form remains available for repair or migration:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider opencode
bash /path/to/ai.skillz/scripts/deploy.sh command commit-msg <repo> \
  --provider opencode
```

The first command is required even if another provider already has the
skill. Command deployment refuses a missing or unhealthy OpenCode skill.

Local deployment creates an ignored absolute
`.opencode/commands/commit-msg.md` link. Submodule deployment creates a
trackable relative link to
`.ai/ai.skillz/providers/opencode/commands/commit-msg.md`. This `ai.skillz`
checkout itself uses a tracked relative link to the canonical provider asset.
There is no corresponding Claude command asset to deploy.
OpenCode discovers the command and skill through its default project
directories, so the script does not mutate `opencode.json` or
`opencode.jsonc`. Quit and restart OpenCode after deployment or update.

## Tracking

Track provider links, `.gitmodules`, and the `.ai/ai.skillz` gitlink only in
submodule mode. Local provider links remain ignored. Nothing is staged unless
`--stage` is explicitly supplied.

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

## What stays local (per-repo)

- `style-guide-reference.md` — your repo's commit style
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

For multi-commit planning, deploy the provider-neutral `commit-plan` companion
after `commit-msg`. `commit-plan` consumes this skill's style, message, runtime,
and safety contracts rather than duplicating them.

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for review context integration
  with `/code-review-changes`)
