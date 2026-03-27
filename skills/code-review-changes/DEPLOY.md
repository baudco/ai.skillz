# Deploying `/code-review-changes`

This skill is fully generic — no per-repo customization
needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/code-review-changes \
      .claude/skills/code-review-changes
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh code-review-changes <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh code-review-changes <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/code-review-changes` → relative symlink
  to `../ai.skillz/skills/code-review-changes`

## Dependencies on other skills

- `/run-tests` — called in step 5 for pre-commit test
  verification. If not deployed, tests are skipped.
- `/commit-msg` — review context files are written for
  this skill to consume during commit generation.

## Prerequisites

- `gh` CLI (authenticated)
- `git` CLI
