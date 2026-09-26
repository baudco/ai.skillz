---
name: plan-io
description: >
  Manage plan file I/O for AI agent sessions. Ensures
  plans and their execution summaries are persisted to
  the repo under `ai/plans/`. Auto-applied
  when entering or exiting plan mode.
compatibility: >
  Works with agentic coding harnesses that write plans.
metadata:
  author: goodboy
  version: "0.1"
disable-model-invocation: true
---

# Plan file I/O conventions

## Directory layout

New durable plan artifacts live under `ai/plans/` in the repo root:

```
ai/plans/
├── <plan-name>.md
└── <plan-name>.summary.md
```

## Rules

### On plan creation

When entering plan mode or writing a plan:

1. Write the plan to
   `ai/plans/<plan-name>.md`
   (NOT only the ephemeral tool-internal location).
2. Use a descriptive `<plan-name>` derived from the
   task (e.g. `init-extraction-plan`,
   `add-auth-feature`, `refactor-api-layer`).
3. Choose the name by subject, not by harness. Before writing,
   check for an existing plan on that subject in `ai/plans/` and
   historical `plans/<harness>/` directories. Revise the relevant
   plan in place when appropriate; do not create parallel copies
   for different harnesses or overwrite an unrelated plan.
4. Start a newly generated plan with YAML front matter:

   ```yaml
   ---
   created_at: 2026-09-25T12:00:00Z
   generated_by:
     harness: opencode
     provider: openai
     model: gpt-6-astra
   ---
   ```

   Set `created_at` to the artifact's actual UTC creation time.
   `harness` names the tool running the agent workflow. Include
   `provider` and `model` only when independently known; do not
   infer one from the harness or the other. Omit unknown fields.
   Preserve `created_at` and `generated_by` when revising a plan:
   they identify its original generation, not its latest editor.
   Describe substantive later human or agent contributions in a
   concise document section or an associated prompt-IO record.
   Git remains the ordinary edit history.

### On plan completion

After executing a plan to completion:

1. Write a summary to
   `ai/plans/<plan-name>.summary.md`
   Give a newly generated summary its own front matter using
   the same identity rules and its actual creation time. Keep
   that watermark on later revisions.
2. The summary follows the project's commit message
   style conventions:
   - Single 50-char summary line
   - Blank line
   - Bullet list of high-level changes/steps
   - Backtick markup around code references
   - Present tense (no past tense)
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
---
created_at: 2026-09-25T12:00:00Z
generated_by:
  harness: opencode
---

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
```

Existing plans and summaries in `plans/<harness>/` stay in place.
Read and revise them without inventing missing metadata or moving
committed references. New subjects use `ai/plans/`.

For example, if OpenCode creates `ai/plans/network-recovery.md`,
Claude Code later edits that same file. Its original
`generated_by.harness: opencode` stays intact. Describe the
substantive Claude Code revision in a `## Contributions` section
or a linked prompt-IO record; do not create a second plan under
`plans/claude/`.
