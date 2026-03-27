# Deploying `/code-review-changes`

## Quick setup

```bash
ln -s /path/to/ai.skillz/skills/code-review-changes \
      .claude/skills/code-review-changes
```

This skill is fully generic — no per-repo customization
needed.

## Dependencies on other skills

- `/run-tests` — called in step 5 for pre-commit test
  verification. If not deployed, tests are skipped.
- `/commit-msg` — review context files are written for
  this skill to consume during commit generation.

## Prerequisites

- `gh` CLI (authenticated)
- `git` CLI
