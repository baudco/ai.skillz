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
  - 648493340b059e6b145a947d4a7b34e252b0d8bf
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

## Original execution-state hardening proposal

Source: `648493340b059e6b145a947d4a7b34e252b0d8bf`, generated with
OpenCode / OpenAI / `gpt-5.6-sol`, as recorded by the source commit.
This fourth slice superseded parts of the historical receipt/journal
proposal with independent mutable plan state and optional mirroring.
It remains deferred evidence, not a shipped state-machine contract.

### Standalone state and optional receipt mirroring

For every plan, create a canonical worktree-private plan-state file beneath the
ignored `commit-msg/msgs/` runtime directory before doing expensive boundary
work. This file is the execution authority whether discovery is approved,
declined, pending or absent; never create a discovery receipt or infer a scan
policy merely to persist a plan. Guard and atomically replace plan state using
its recorded prior digest and a fresh writer token.

The proposal's versioned schema is retained beside this reference in
`deferred-commit-plan-resources/receipt-extension.schema.json`.
Its original deployed location was
`skills/commit-plan/references/receipt-extension.schema.json`.
Derive each stable boundary ID from canonical JSON containing its
repository ID, ordinal, sorted paths, expected parent reference,
staged tree and patch digest. Derive the stable plan ID from the
task digest, ordered repository IDs, initial parent and ordered
boundary IDs. Serialize with sorted keys, UTF-8 and no optional
whitespace. The schema records starting index digests and, per
boundary, exact parent/tree evidence, message and check records,
dependencies, boundary-owned review replies and completion state.

When a valid exact-key receipt already exists, mirror the same plan-state
object into `extensions.commit-plan`. Every mirror creation or mutation,
including completion updates after human commits, must use `/git-mgmt`'s
pointer transaction: publish `receipt_sha256: null`, atomically replace the
receipt, then publish its new digest. The pointer's scan policy remains
authoritative. A missing, declined, corrupt or pending receipt leaves the
standalone plan state authoritative and receives no extension update.

Assign each pending reply to exactly one stable boundary using review context
and changed-path evidence. Ask when ownership is ambiguous; never let the first
new `HEAD` consume replies owned by later boundaries.

### Journal, isolation and completion finalization

Before invoking the editor, durably journal the boundary ID, expected
parent/tree, patch and message digests, helper writer token, pointer/receipt
digests when present, standalone plan-state path/digest, real-index
path/digest and exact stage entries, isolated-root digest, and phase.

After exact parent/tree completion, the helper's durable finalization phase
updates standalone plan state, mirrors it only when a valid receipt was already
attached, and prepares every reply candidate assigned to that boundary from
its recorded local source file. It replaces only the pending-commit marker,
writes the boundary-owned candidate, records its digest and prints the complete
candidate plus publication coordinates. Missing source evidence stops that
reply without consuming later replies. Candidate creation never authorizes
publication; `/gish comment-edit` still requires separate exact approval.

The durable journal authorizes the helper to resume its own matching standalone
state transaction and, when attached, its matching pointer/receipt transaction
under `/git-mgmt`'s writer-continuation rule. It never creates or attaches a
receipt during recovery. On rerun after `HEAD` advanced, classify before doing
anything else:

- expected parent and tree: finish index reconciliation, attached-receipt
  publication and completion/reply finalization, then return successful
  already-complete no-ops;
- expected parent but a different committed tree, including hook-modified
  private-index content: record `diverged-after-commit`, never commit again and
  stop for replanning;
- any unrelated parent/ancestry change: stop without staging or committing.

The slice reiterated that commands, project checks and commit hooks
must run against both the exact private index and isolated execution
root. Its completion gate required private-index reconstruction,
isolated checks/editors/hooks, schema-valid standalone state with
byte-equivalent attached receipt state, and finalization of only the
completed boundary's assigned candidates with a separately approved
publication handoff. These are comparison requirements, not evidence
that the old helper or recovery phases exist.

### Shared review/regression context ownership

Before the first message, snapshot review and regression context into the
plan-state artifact and assign each applicable context record to its exact
boundary or boundaries. Invoke `/commit-msg` with only that boundary's scoped
snapshot. During composition, `/commit-plan` owns cleanup: `/commit-msg` must
not delete shared context after the first message. Remove regression context
only after every assigned message is archived. Preserve review context and
reply source files until every assigned local candidate is prepared and every
separately approved publication succeeds.

The incoming commit-message changes distinguished standalone
single-use context from orchestrator-owned boundary snapshots:
standalone regression context is deleted after its message;
standalone review context remains when reply candidates need the
real commit hash. Composition must leave shared context and reply
files with the orchestrator and must not delete review context when
another assigned boundary still needs the trailer.

The boundary helper's durable finalization phase prepares those candidates
immediately after verified commit completion, records their paths/digests in
plan state and prints their complete bodies and publication coordinates. On
a follow-up session, rerunning that boundary helper's `ensure` operation or
refreshing `/commit-plan` by stable plan ID resumes any incomplete candidate
finalization without repeating the commit.

### Git-management extension proposal

`extensions.commit-plan`, when present, must validate against the proposal's
schema asset and must be byte-equivalent to that plan's canonical standalone
state. This requirement was moved out of the active Git-management skill.

A composing skill may persist independent worktree-private state, but it may
attach or mirror an extension only when the pointer already names a valid
exact-key receipt. Missing, declined, corrupt or pending receipt evidence must
not be repaired by inventing `scan_policy` or creating a discovery receipt.

### Historical resources and verification limits

The schema and fixture bytes are retained unchanged under
`deferred-commit-plan-resources/`. The historical fixture-check script
is retained there with adjacent-resource paths, wrapped source and
docstrings scoped to historical evidence. These checks cover required
keys, selected lifecycle values, parent-source exclusivity, sorted
paths and JSON round-tripping. They do not perform full JSON Schema
validation or demonstrate implemented interruption recovery.
Deployment checks inspect this deferred reference and run those
fixture checks without deploying the old schema as an active asset.

The original Prompt-IO summary and raw record retain their historical
paths and generation metadata. They describe the original experiment,
not the current resolution. Compare the standalone state, mirroring,
journal, finalization and context snapshot layers against a minimal
immutable pending-tail revision workflow before adding any of them.

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

All four rebased slices are preserved here or in adjacent historical
resources. Their successful replay does not activate the deferred
proposal or replace the shipped operational contract.
