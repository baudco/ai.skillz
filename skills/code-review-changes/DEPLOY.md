# Deploying `/code-review-changes`

The skill content is generic and deploys as a whole-directory link. Its
review handoff files are worktree-local runtime state.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh code-review-changes <repo> \
  --provider <claude|opencode|all>
```

Provider destinations are `.claude/skills/code-review-changes` and
`.opencode/skills/code-review-changes`. Local mode uses ignored absolute
links; submodule mode uses trackable relative links through `.ai/ai.skillz`.

Existing `.claude/review_context.md` and
`.claude/review_regression.md` files remain local and are never moved or
overwritten by source deployment or migration. Track provider links only in
submodule mode, together with `.gitmodules` and the anchor gitlink. Nothing is
staged unless `--stage` is explicitly supplied.

Quit and restart OpenCode after deployment or update. The default
OpenCode skill directory works without config mutation.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

`status` can report unportable OpenCode `skills.paths`, but deployment
does not edit `opencode.json` or `opencode.jsonc`. Review the migration
dry run before applying it. Use `update` only for a submodule anchor.

## Dependencies on other skills

- `/run-tests` — called in step 5 for pre-commit test
  verification. If not deployed, tests are skipped.
- `/commit-msg` — review context files are written for
  this skill to consume during commit generation.

## Prerequisites

- `gh` CLI (authenticated)
- `git` CLI
