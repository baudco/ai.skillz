---
title: Deferred commit-plan private-index execution experiment
status: deferred-design
harness: opencode
provider: openai
model: gpt-6.1-sol
created: 2026-10-04
source_commit: 8fd71ed12e32beabbc7011f308bf5ebcf700d613
additional_source_commits:
  - 7796acbe2d4d914d863d21ba71079ddb629afd73
  - 5424f11f63206ce0856c241f3672d77ee927f147
source_harness: opencode
source_model: gpt-5.6-sol
source_provider: openai
---

# Deferred private-index execution experiment

This reference preserves historical slices of the older bot-generated
design while rebasing it onto the shipped builder/executor. It is
design evidence, not an active skill instruction or a claim that the
interfaces below are implemented. Source generation metadata remains
separate from this reference's generation metadata.

## Activation condition

Prefer the shorter path: compose the existing `plan-build.py` and
`plan-exec.py` for authenticated pending-tail revision, exact-prefix
classification, immutable replacement packages and index preservation.

Revisit this more extensive experiment only if reproducing ordinary
revision, interruption or competing-writer cases shows that the shorter
path cannot meet its agreed contract. Record that failure and the
smallest missing guarantee before introducing additional state.
An experimental active-skill overhaul may be necessary then; it is
not authorized or activated by preserving this document.

Keep the canonical skill and deployed execution behavior unchanged
during design comparison. Evaluate the proposal rather than require
agents to generate this machinery for each new plan. No rebase,
implementation result or passing check implies human acceptance.

## Original first-slice execution requirements

The following is the incoming proposal, not current operational policy:

Generate deterministic cached patches and a per-boundary execution helper
beneath the ignored `commit-msg/msgs/` runtime directory for every plan, not
only partial-file boundaries. Do not use an interactive patch console. The
helper must construct a private boundary index from the evidenced parent tree
and apply the exact cached patch there; it must never depend on the user's
current staged state. Reference it explicitly in the final command sequence.

The helper must support idempotent `ensure` and `run -- <command>` operations:

- recognize an already completed boundary from the recorded parent/tree chain,
  print a concise skip notice and exit successfully;
- otherwise require the evidenced parent relationship, recreate the private
  index from that parent and apply/verify the recorded patch and staged tree;
- populate an isolated execution root from the verified private index, then
  execute every `run` command from that root with `GIT_DIR` naming the active
  worktree's private Git directory, `GIT_WORK_TREE` naming the isolated root and
  `GIT_INDEX_FILE` naming the private index. Checks, editors and hooks must not
  read later-boundary or unrelated live-worktree content;
- reject unexpected `HEAD`, parent, patch, tree or message-digest changes
  instead of guessing, duplicating a commit or overwriting worktree content;
- before invoking the editor, durably journal the boundary ID, expected
  parent/tree, patch and message digests, helper writer token, pointer/receipt
  digests, real-index path/digest and exact stage entries, and phase;
- after a successful wrapped commit, verify its parent/tree and reconcile the
  real index with a temporary three-way transition using the expected parent as
  base, the committed tree as the new base and the execution-time real index as
  user state. Atomically install it only if the real-index digest still matches;
  preserve all non-boundary and non-overlapping staged changes and all worktree
  content. On overlap or compare-and-swap failure, leave the real index bytes
  untouched and report the required reconciliation instead of replacing whole
  entries by path;
- make interruption before, during or after the editor safe to rerun. A helper
  rerun must either resume the same pending boundary or recognize its exact
  committed tree; it must never create a second commit for it.

The durable journal authorizes the helper to resume only its own matching
pointer/receipt transaction under `/git-mgmt`'s writer-continuation rule. On
rerun after `HEAD` advanced, classify before doing anything else:

- expected parent and tree: finish index reconciliation, receipt publication
  and completion recording, then return successful already-complete no-ops;
- expected parent but a different committed tree, including hook-modified
  private-index content: record `diverged-after-commit`, never commit again and
  stop for replanning;
- any unrelated parent/ancestry change: stop without staging or committing.

Hook-modified or unrelated commits are necessary errors, not idempotent skips.
Message-only editor or hook changes remain valid because completion is based on
parent/tree relationships rather than the final commit OID or message text.

## Original rendering and retention requirements

The same slice proposed a helper `ensure` before each boundary and
helper-wrapped checks, review and editor-backed commit operations:

Deferred interface rule: Do not render raw `git add` operations.

Wrap every per-boundary check, review and commit command as
`<boundary-helper> run -- <command>`. This keeps `git diff --staged` and the
mandatory `git commit --edit --file ...` visible in the rendered sequence while
running them against the exact private index and isolated execution root. Do not
render raw `git add`,
`git restore --staged`, `git reset` or `git apply --cached` commands whose
result depends on the caller's staged state. Every rendered line must succeed
as a no-op when its boundary is already complete, so the full command block can
be rerun after partial or complete execution without needless errors or
duplicate commits.

The proposal also retained execution journals/private index snapshots
until durable completion or explicit divergence, compared each staged
diff against its own recorded parent, and delayed shared-context
cleanup until boundary-owned finalization. These remain design choices
to compare with the existing executor, not requirements for callers.

## Original Git-management continuation proposal

This paragraph was moved out of the active Git-management skill:

An exact writer may resume its own interrupted transaction without that human
recovery flow when a durable journal supplies the same task, target, prior
digest, writer token and intended replacement digest. Re-read and compare every
field before continuing the recorded next phase. This is owner continuation,
not stale-guard takeover: any mismatch stops and requires explicit recovery.

## Original parser-safe rendering proposal

Source: `7796acbe2d4d914d863d21ba71079ddb629afd73`, generated with
OpenCode / OpenAI / `gpt-5.6-sol`, as recorded by the source commit.
This second slice is deferred comparison evidence. The shipped skill
already selects the parser by evidence and validates native rendering;
its Xonsh and Bash renderers use native bindings and continuations.
The blanket single-line and environment-overlay rules below conflict
with that shipped interface and are not activated by this reference.

Choose the active command parser from evidence in this order:

1. an explicit parser or shell selected by the user for this command block;
2. harness-reported command parser metadata from the active provider session;
3. parser semantics already demonstrated by successful or failed commands in
   the current session;
4. the actual parent/ancestor command interpreter reported by process metadata
   or an equivalent provider diagnostic;
5. the basename of `$SHELL`, only as a last-resort hint.

Do not equate inherited login-shell metadata with the active parser. In
particular, `$SHELL=sh` does not override harness or observed xonsh evidence.
Report every conflicting signal and which higher-priority evidence won. If
equal-priority evidence remains ambiguous, ask which parser to target before
rendering rather than silently choosing `$SHELL`.

Use the selected parser as the single Markdown fence language and command
syntax. Render every command on one physical line for every parser. Never use
a trailing `\` or any other newline-continuation syntax; pasted continuation
lines are parser-sensitive and can become separate or invalid commands.

Render environment overlays portably as `env KEY=value command` (and
`env KEY1=value1 KEY2=value2 command` for multiple values) in every shell.
Never emit a leading `KEY=value command` assignment or parser-specific
environment syntax. When the target is a shell builtin or function that
cannot run through `env`, put the overlay inside a generated helper or an
explicit parser subprocess instead.

The returned sequence must use one explicitly labelled fence and valid syntax
for the selected parser. Never emit an unlabelled fence or hardcode POSIX
syntax for a different parser.

The slice also proposed checking the evidence hierarchy, reporting
conflicting signals, and requiring every command to occupy one physical
line with every environment overlay using `env` or a generated helper.
Its standalone commit-message example collapsed the editor-backed
commit to one line, but used the historical hardcoded Claude path.
For comparison, retain the current runtime-neutral placeholder:

```text
git commit --edit --file <commit_latest>
```

Historical deployment assertions now inspect this reference for parser
precedence and rendering rules. The available-shell `env` smoke check
is retained as a portability check, not evidence that the deferred
policy is required or implemented by the active renderer.

## Original boundary-owned review-reply proposal

Source: `5424f11f63206ce0856c241f3672d77ee927f147`, generated with
OpenCode / OpenAI / `gpt-5.6-sol`, as recorded by the source commit.
This third slice proposes reply ownership as part of the deferred
receipt/helper design. It is not an implemented reply-ownership API
in the shipped builder/executor. Preserve the active local-candidate
and separately approved publication lifecycle during comparison.

The historical receipt proposal added assigned review-reply IDs to
each stable boundary's `extensions.commit-plan` record alongside
checks/outcomes, dependency IDs and completion state:

Assign each pending reply to exactly one stable boundary using review
context and changed-path evidence. Ask when ownership is ambiguous;
never let the first new `HEAD` consume replies owned by later boundaries.

Its materialization step added:

Record boundary-owned review replies and defer their candidate generation
until that exact boundary's parent/tree completion is verified. Completion
of another boundary must not consume them.

The incoming commit-message composition paragraph was moved here:

When composed by `/commit-plan`, do not render this standalone handoff.
Preserve the review-reply lifecycle, but let `/commit-plan` render the
archived message path and helper-wrapped `git commit --edit --file ...`
command for the exact boundary index. Assign every `reply_id` to one stable
boundary before rendering the plan; if repository evidence cannot determine
ownership, ask rather than attaching it to the next commit. A new `HEAD`
processes only replies assigned to the exact boundary whose parent/tree
completion `/commit-plan` verified. Defer replies owned by later boundaries.

For a standalone commit, once the user confirms it (or a new `HEAD` is
detected), the real commit hash is known. For each reply ID, read its exact
local source body from the corresponding `reply_files` entry written by
`/code-review-changes`. If an entry is missing, stop for that reply; do not
fetch remote content or reconstruct it from memory.

Historical ownership/deferral assertions now inspect this reference.
Compare a minimal reply-to-boundary mapping bound to immutable plan
evidence with the old receipt extension before choosing storage or
adding helper machinery. Neither verified completion nor candidate
generation authorizes publication or changes human-owned task states.

## Comparison questions

- Which requirements are already satisfied by shipped immutable specs,
  private indexes, exact-tree/history validation and publication locks?
- Which evidenced interruption cases need an additional durable journal?
- Can pending-tail revision and explicit supersession solve the ordinary
  human iteration case without receipt mirrors or generated helpers?
- Allow concurrent readers/planners, but serialize or refuse conflicting
  HEAD/index mutation in one worktree. Do not imply unrestricted parallel
  staging and commits are safe.
- Measure code/state complexity, planning latency and recovery effort
  against the shorter path before adopting an alternative.

Later rebased slices may add their historical ideas to this reference
or adjacent design resources. They must not silently replace the
shipped operational contract merely because their patches replay.
