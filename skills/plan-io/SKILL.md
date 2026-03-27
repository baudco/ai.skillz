---
name: plan-io
description: >
  Manage plan file I/O for AI agent sessions. Ensures
  plans and their execution summaries are persisted to
  the repo under `plans/<ai-service>/`. Auto-applied
  when entering or exiting plan mode.
compatibility: >
  Designed for Claude Code (or similar agentic coding
  tools with plan-mode capabilities).
metadata:
  author: goodboy
  version: "0.1"
disable-model-invocation: true
---

# Plan file I/O conventions

## Directory layout

All plan artifacts live under `plans/` in the repo
root, namespaced by AI service:

```
plans/
└── <ai-service>/          # e.g. claude, copilot, cursor
    ├── <plan-name>.md
    └── <plan-name>.summary.md
```

## Rules

### On plan creation

When entering plan mode or writing a plan:

1. Write the plan to
   `plans/<ai-service>/<plan-name>.md`
   (NOT only the ephemeral tool-internal location).
2. Use a descriptive `<plan-name>` derived from the
   task (e.g. `init-extraction-plan`,
   `add-auth-feature`, `refactor-api-layer`).
3. The `<ai-service>` is the name of the AI coding
   tool generating the plan (e.g. `claude`, `copilot`,
   `cursor`, `windsurf`).

### On plan completion

After executing a plan to completion:

1. Write a summary to
   `plans/<ai-service>/<plan-name>.summary.md`
2. The summary follows the project's commit message
   style conventions:
   - Single 50-char summary line
   - Blank line
   - Bullet list of high-level changes/steps
   - Backtick markup around code references
   - Present tense (no past tense)
   - Trailing `claude-code` attribution footer
3. Include a `## Deferred` section if any planned
   items were not completed.
4. Include a `## Stats` section with counts
   (commits, files, errors, etc.).

### Context management

- Only clear/compress context if over 60% used.
- Do NOT proactively compress just because a plan
  phase completed.

## Example summary

```markdown
Refactor authentication into middleware layer

- Extract auth logic from route handlers into
  `middleware/auth.py`
- Add `@require_auth` decorator for protected routes
- Move token validation to `utils/tokens.py`
- Update 12 route handlers to use new middleware
- Add tests for middleware in `tests/test_auth.py`

## Deferred

- OAuth2 provider support (separate plan)

## Stats

- 3 commits, 14 files changed
- All tests passing

(this patch was generated in some part by
[`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```
