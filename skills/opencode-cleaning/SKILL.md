---
name: opencode-cleaning
description: >
  Preview and delete stale OpenCode fork sessions for the current repository.
  Use when session history contains disposable `(fork #N)` copies or the user
  asks to clean OpenCode session state safely.
compatibility: >
  Requires Python 3 and an OpenCode CLI with JSON session listing and session
  deletion support.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[--older-than-days N] [--directory PATH]"
---

# OpenCode Cleaning

Clean stale fork sessions with a fail-closed preview and apply workflow. Read
this skill completely before running its helper.

## Why Titles Are Used

OpenCode 1.18.13 does not expose fork lineage in
`opencode session list --format json`. Its fork implementation creates a new
root session without `parentID` and generates titles using the exact form:

```text
<non-empty base title> (fork #<positive integer>)
```

The helper therefore uses the full anchored pattern, not merely
`endswith('(fork #1)')`. `parentID` identifies subagent sessions, not UI
forks, and the CLI root-session list omits those children.

Re-check tagged OpenCode source before changing this classifier for a new
major session format.

## Safety Boundary

The initial cleaning request authorizes discovery and preview only.

- Never delete during the first invocation.
- Never inspect or mutate OpenCode's SQLite database directly.
- Never infer that every old session is disposable.
- Limit candidates to one exact resolved directory.
- Require the canonical full fork-title pattern.
- Default to sessions not updated for seven days.
- Always protect the newest listed session in the selected directory.
- Never broaden to `~`, sibling repositories, or every OpenCode project.
- Do not rename, archive, share, compact, or otherwise mutate sessions.

## Preview

Run the bundled helper from the selected repository:

```text
python <skill-dir>/scripts/opencode-cleaning.py
```

Optional arguments:

```text
--directory <path>       exact repository directory; defaults to cwd
--older-than-days <N>    non-negative age threshold; defaults to 7
--opencode <path>        alternate OpenCode executable for testing
```

The helper invokes OpenCode in pure mode, validates every JSON record, prints
the protected session and candidate IDs/titles/ages, and emits a selection
token. It writes no files.

If there are no candidates, stop. Do not weaken filters automatically.

## Human Approval

Present the complete candidate list, directory, age threshold, protected
session, and selection token. Wait for a follow-up message explicitly
approving deletion of that exact token.

The initial request, approval of an earlier candidate list, silence, blanket
cleanup permission, or approval of a title pattern is not enough.

If the user changes the directory, threshold, or selected sessions, run a new
preview and obtain approval for its new token.

## Apply

After exact follow-up approval, run:

```text
python <skill-dir>/scripts/opencode-cleaning.py \
  --directory <path> --older-than-days <N> --apply <token>
```

The helper recomputes the complete selection. Any changed candidate title or
timestamp, candidate set, protected session ID/title, directory, or threshold
invalidates the token and prevents deletion. The protected active session's
timestamp may advance while the user reviews the preview without invalidating
the token.

Deletion is sequential because OpenCode provides no transaction. Stop on the
first failure, report sessions already deleted, and require a fresh preview
before retrying.

## Report

Report:

- selected directory and threshold;
- protected session ID;
- deleted session IDs and titles;
- the first failure, if any;
- whether a fresh preview is required.

Do not claim database compaction or immediate RSS reduction. Session deletion
removes history; its storage and runtime effects remain OpenCode-owned.
