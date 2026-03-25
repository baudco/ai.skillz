---
name: inter-skill-review
description: >
  Audit a set of skills that compose into a
  workflow pipeline. Verify cross-skill contracts,
  shared artifacts, step ordering, and coverage
  gaps. Use after building or refining skills that
  call each other.
argument-hint: "[skill-names or skill-paths]"
disable-model-invocation: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Edit
---

When auditing a multi-skill pipeline, follow this
process:

## 0. Identify the skill graph

- Read each skill's `SKILL.md` in full.
- Map which skills reference other skills (look
  for `/skill-name` invocations, shared file
  paths, or "see the X skill" cross-refs).
- Draw the dependency graph, e.g.:
  ```
  /code-review-changes
    ├─ calls /run-tests (step 5)
    └─ writes artifact for /commit-msg (step 5.2)

  /run-tests
    └─ standalone, no outbound deps

  /commit-msg
    └─ reads artifact from /code-review-changes
  ```
- Present this graph to the user before
  proceeding.

## 1. Verify shared artifacts

Skills often communicate via files (context
files, output files, state markers). For each
shared artifact:

- **Producer**: which skill writes it, at what
  step, in what format?
- **Consumer**: which skill reads it, at what
  step, what fields does it expect?
- **Lifecycle**: when is it created, when is it
  deleted, what happens if it's missing?
- **Location**: is the path relative to repo
  root, worktree root, or `~/.claude/`? Does it
  work correctly in worktree contexts?

Flag any mismatches: producer writes fields the
consumer doesn't read, consumer expects fields
the producer doesn't write, file lives in the
wrong directory for the worktree case, etc.

## 2. Check step ordering across skills

When skill A invokes skill B mid-workflow, verify:

- **Preconditions**: does skill B assume state
  that skill A has set up? (e.g. venv exists,
  worktree is active, files are staged)
- **Postconditions**: does skill A depend on
  output from skill B before continuing?
  (e.g. test results before posting comments)
- **Temporal conflicts**: does any step in A
  require an artifact that only exists after a
  step the user performs manually between A and
  a later skill? (e.g. commit hash needed for
  comments but commit is manual)

For each temporal conflict, verify there's an
explicit strategy documented (placeholder +
update, deferred execution, follow-up
invocation, etc.).

## 3. Check human-in-the-loop boundaries

Identify every point where control passes to the
human (manual staging, committing, pushing,
reviewing). For each:

- Is the handoff clearly documented in the
  skill that yields control?
- Does the next skill (or next step in the same
  skill) know how to resume after the human
  acts?
- Are there instructions for what the human
  should do and what the skill expects back?

## 4. Check for duplicated instructions

When multiple skills cover the same ground (e.g.
worktree venv setup appears in both
`/code-review-changes` and `/run-tests`):

- Is the guidance consistent between them?
- Could one skill delegate to the other instead
  of repeating? If so, suggest consolidation.
- If duplication is intentional (standalone use
  vs. composed use), verify the instructions
  don't diverge.

## 5. Verify error/regression accountability

When a composed workflow can cause regressions
(skill A's changes break something that skill B
detects):

- Is there a clear chain of accountability?
  (who caused it, how it was found, how it's
  reported)
- Does the reporting flow through to the user
  via commit messages, GH comments, or other
  artifacts?
- Is the self-caused vs. pre-existing
  distinction documented?

## 6. Present findings

Organize findings as:

### Coverage gaps
Things the pipeline should handle but doesn't.

### Ordering issues
Steps that assume state that may not exist yet.

### Artifact mismatches
Shared files with producer/consumer misalignment.

### Duplication
Repeated instructions that could diverge.

### Suggested changes
Concrete edits, grouped by skill file.

For each finding, ask the user how they want to
resolve it (via `AskUserQuestion`) before making
changes. Present options where multiple valid
approaches exist.

## 7. Apply approved changes

After user sign-off:

- Edit each skill file with the agreed changes.
- Re-read all modified skills to verify
  consistency.
- Present a final diff summary per skill.

## When this skill runs

**This skill is self-triggering.** The model
MUST run this review process (silently, in the
background) every time ANY skill is added,
extended, simplified, or refined - without
waiting for the user to invoke
`/inter-skill-review`.

After completing a skill change, immediately:

1. Glob for all `SKILL.md` files in
   `~/.claude/skills/` and the repo's
   `.claude/skills/`.
2. Identify which skills reference or are
   referenced by the one that just changed.
3. Run steps 0-5 on the affected subset.
4. If no issues found, proceed silently.
5. If issues found, present findings to the
   user (step 6) before they move on.

The user can also invoke `/inter-skill-review`
explicitly for a full audit across all skills,
or to debug a cross-skill workflow failure.
