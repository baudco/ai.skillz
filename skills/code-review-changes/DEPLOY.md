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
OpenCode skill deployment installs its dependent command shim automatically;
use `--no-command` only for an intentional skill-only deployment.

Existing `.claude/review_context.md` and
`.claude/review_regression.md` files and `.claude/review_replies/` candidates
remain local and are never moved or overwritten by source deployment or
migration. Track provider links only in
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

- `/gish` — required provider-neutral PR identity and reply transport. Deploy
  it before this skill; manifest dependency checks enforce its availability.
- `/open-wkt` — required companion for ownership-safe review worktrees. Stop
  cleanly if it is unavailable rather than creating an unmanaged worktree.
- `/run-tests` — called in step 5 for pre-commit test
  verification in every repository receiving fixes.
  Deploy it first; review fixes stop if it is absent.
- `/commit-msg` — review context files are written for
  this skill to consume during remote-review commit
  generation. Local Tuicr reviews do not write the
  forge-specific context file.

## Prerequisites

- `gh` CLI (authenticated)
- `git` CLI
- For local reviews, the user's existing `tuicr` command
  and its normal `HOME`/XDG environment. No forge login is
  required.
