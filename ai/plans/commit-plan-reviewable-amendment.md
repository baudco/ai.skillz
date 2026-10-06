---
created_at: 2026-10-06T21:18:08Z
generated_by:
  harness: opencode
  provider: openai
  model: gpt-6.1-sol
---

# Reviewable commit-plan amendment

## Purpose and delivery boundary

Extend the canonical commit-plan builder/executor with reviewable
amendment support. This plan tightens the user-supplied implementation
brief; preserving it does not claim implementation or acceptance.

Read AGENTS.md and the applicable layered-design, py-codestyle,
commit-plan, commit-msg, run-tests and code-nav-refs contracts first.
Inspect the implementation and meaningful Git tests before editing:

- `skills/commit-plan/SKILL.md:1`
- `skills/commit-plan/scripts/plan-build.py:1`
- `skills/commit-plan/scripts/plan-exec.py:1`
- `skills/commit-msg/SKILL.md:1`
- `skills/code-nav-refs/SKILL.md:1`

Keep workflow logic in shared tooling. Do not generate an amendment
script per plan or revive the deferred journal/receipt architecture
wholesale. Compare with the shipped #24 builder/executor and the
deferred design evidence in PR #25.

Deliver the implementation, validation results and a reviewable
commit-plan package. Do not commit, amend, push, reset or rebase on the
agent's own initiative. Do not change user-owned task state markers.

## 1. Bound the first version

Support two planning entry points:

1. Explicit skill invocation with `--amend`: prepare a package to
   replace the recorded current HEAD. It contains exact correction
   boundaries, a complete editable message, checks and native rendering.
2. Dynamic selection: an eligible ordinary single-boundary package
   contains authenticated append and amend alternatives prepared before
   execution. After review, offer commit, amend and abort. Ineligible
   ordinary packages retain their existing commit/abort behavior.

Initial amendment eligibility requires exactly one boundary, an
existing single-parent target commit, and the same recorded branch and
worktree with HEAD still at that target. Refuse root/merge amendment,
multi-boundary amendment, and amendment of an earlier completed
boundary. Explain the failed condition and recommend preparing a new
supported package or a separately designed history operation.

Ordinary multi-boundary, root-based and merge-based append planning
must retain its currently supported behavior. An ineligible amendment
alternative must not invalidate an otherwise valid ordinary plan.

Do not add remote-history discovery or assume that a published commit
may be rewritten. Amendment authorizes no force-push or publication.
Later multi-boundary support needs a separate progress-model design.

## 2. Keep operation identities explicit

Separate these concepts in the pinned specification:

- Expected branch HEAD: the OID compared during publication.
- Replacement target: the original commit being amended, if any.
- Result parent: the parent the newly created commit must have.
- Result tree: the complete resulting commit tree.
- Correction base/tree: the old HEAD and its original tree.
- Operation: append or amend, with its own authenticated message and
  check context.

For append, the result parent is the expected branch HEAD. For amend,
the result parent is the replacement target's original parent; the
publication compare-and-swap still expects the replacement target OID.
Do not overload one `parent_oid` variable for these different roles.

Specify the versioned operation schema and compatibility rule before
adding helpers. Preserve existing ordinary package behavior. Treat
unknown or malformed amendment claims as errors, not append defaults.

## 3. Preserve author and message semantics

Capture the original raw author identity: name, email, author timestamp
and timezone. Preserve it exactly unless the human explicitly requests
a different authenticated operation. Use normal new committer metadata.
Capture the original parent and reject hook-produced parent/tree/author
changes before publishing the detached result.

An amendment starts from the original complete message and incorporates
the planned corrections; it is not merely a correction-only message.
Retain relevant trailers and provenance according to commit-msg.
Prepare a separate complete append message for the dynamic alternative.
Authenticate both artifacts before review and keep the chosen message
role-bound. Never change a pinned spec or substitute another message
because the human chose amend after seeing the staged diff.

The editor may change the selected message text. Its edited contents
are not a reliable completion key. Define signing behavior consistently
with existing Git policy; do not silently drop configured signing or
promise preservation of the original signature after rewriting content.

## 4. Preserve planning and review guarantees

Planning may write a new immutable package and temporary evidence, but
must preserve the real index's bytes/metadata and Git refs/history.
Never execute project checks during planning without the existing
explicit pre-execution request. Never enter an editor during planning.

Keep the execution flow understandable:

1. Authenticate the package and all offered operation artifacts.
2. Recheck identity, HEAD and the recorded index state.
3. Stage only the planned corrections; refuse unsupported overlapping
   or unrelated index state without discarding it.
4. Run structural and selected project checks for offered operations.
5. Show the labelled review scopes and operation/message summaries.
6. Obtain the explicit post-review action choice.
7. Open the selected complete message in the commit editor.
8. Verify the private result, then publish with the expected-HEAD CAS.

For an amendment-capable package, show both review scopes with visible
labels in the review output before authorizing amendment:

- Corrections: old HEAD tree to planned result tree.
- Complete amended commit: original parent tree to planned result tree.

After pager exit, repeat the action choices and target summary. Pager
navigation must never count as amendment approval. Keep sanitized diff,
pager handling and `--no-pager` behavior consistent with the executor.

## 5. Define the post-review action contract

For an eligible dynamic package, empty Enter retains the ordinary
commit default. Only an explicit typed `amend` or deliberate supported
selection may choose amendment. Explicit amendment-only packages also
require an explicit amendment choice after review; empty input cannot
rewrite HEAD and must not fall through to an unprepared append action.

Support abort without entering the editor. On invalid answers, explain
the accepted choices and reprompt without choosing an operation.
Ctrl-C aborts with interruption status; EOF aborts without a selection.
Do not introduce a blanket yes flag which defaults to amendment.

In the first version, noninteractive amendment is unsupported and fails
with an actionable instruction to rerun interactively. Existing
noninteractive ordinary-commit behavior remains unchanged. Do not
infer an amendment choice from lack of a terminal, piped empty input,
the planning flag, a previous agent message or a normal-commit default.

## 6. Make checks operation-aware

The same result tree can have different history under append and amend.
Run checks in the selected operation's correct Git context, including
its effective parent. Do not run amendment checks with the old HEAD as
the new parent merely because that is the current append implementation.

Dynamic packages must prepare the check definitions for both offered
operations. To preserve the checks-before-review ordering, validate
both contexts before offering the choice. Display any extra check cost.
Reuse a check across operations only when its documented full identity
and evidence establish that the differing history is irrelevant;
otherwise execute separately. Do not infer this from identical argv or
trees, and do not invent a new broad PASS cache.

Prior PASS reuse must bind the effective operation/history context,
exact tree, argv, environment, resolution probe and prerequisites.
Without matching evidence the check remains pending. Include a test
whose result actually depends on parent/history, not only file bytes.

## 7. Recognize replacement without confusing same-tree commits

Existing completion classification expects an append-only parent/tree
chain. Adding `--amend` to commit argv is insufficient.

Amendment remains pending while HEAD is the recorded replacement
target. Message-only amendment is supported: the result can have the
same parent and tree as that target. Therefore parent/tree equality
alone must never declare the original target already completed.

Define a minimal owned execution record only for the new guarantees
that cannot be recovered from immutable inputs and history. Bind it to
the specification digest, operation identity, target, branch/worktree,
selected artifact roles and writer ownership. Do not mirror it into
discovery receipts or create a competing generic workflow state machine.

Persist the selected action before entering the editor. After editor
success and verification, durably record the exact candidate commit
OID before attempting branch publication. A rerun can then distinguish
an unpublished candidate from that exact published replacement even
when its parent/tree are unchanged. Refuse mismatched or unowned state;
never silently take over another writer's selection or replace it with
the new invocation's default choice.

Publish from the detached checkout using the old target as the expected
branch OID, while preserving the existing HEAD/index/branch locks and
artifact rechecks. Handle process death around candidate recording,
ref publication and completion recording without claiming crash-atomic
Git transactions. Preserve owned recovery evidence and report what the
human must inspect when safe automatic resumption is impossible.

Editor abort leaves a recoverable pending operation. Rerunning a
completed operation performs no staging, checks, editor, hooks or new
amendment. Unexpected branch movement, unrelated replacements and
hook-produced identity/parent/tree drift fail closed. An unchanged-OID
editor result needs a deliberate diagnostic; never misclassify the
original target as a newly published replacement.

## 8. Focused verification matrix

Use real temporary repositories and inspect raw Git objects, refs,
index contents and editor/hook invocations. Cover:

- Explicit content amendment and message-only amendment.
- Dynamic commit default, explicit amend, abort, invalid input,
  Ctrl-C, EOF and noninteractive refusal.
- Root, merge, multi-boundary and changed-target eligibility refusal
  without regressing supported ordinary append packages.
- Authenticated message selection, original complete message/trailers,
  preserved author name/email/date/timezone, and original parent.
- Both labelled review scopes and a history-sensitive project check.
- Editor abort/resume and a completed-operation no-op, including
  message-only same-tree replacement and unchanged-OID handling.
- Interruption before editor, after private candidate creation, around
  ref publication and before completion recording.
- Writer/selection/artifact drift, index/ref drift, and hook-produced
  parent/tree/author changes with no unintended branch publication.
- Unrelated staged and unstaged content: exact preservation on refusal
  or completion, with no accidental inclusion in the result.
- Native Xonsh rendering, no-startup compilation, matching command
  previews, and read-only preflight/show modes.
- The existing ordinary planner/executor and deployment regressions.

## 9. Implementation sequence and handoff

1. Trace the current builder, classifier, review gate, detached commit,
   locks and CAS publication. Write the operation/persistence contract
   and public workflow before introducing helper APIs.
2. Implement bounded explicit amendment with authenticated inputs,
   exact author/parent preservation and replacement-aware recovery.
3. Implement eligible dynamic alternatives and the post-pager action
   prompt without weakening ordinary default behavior.
4. Update shared validation/schema logic, CLI help, renderer, skill
   instructions and handoff validation consistently with that contract.
5. Apply py-codestyle and verify repository license-header conventions
   before adding notices; preserve existing ownership and license.
6. Run focused Git-behavior tests and required repository validation:
   `bash scripts/validate-skills.sh`,
   `bash tests/deploy/test-deploy.sh`, and
   `bash scripts/validate-deployment.sh .`.
7. Report exact results and remaining unsupported cases; produce the
   complete reviewable commit-plan handoff. Leave execution and task
   acceptance to the human.

## Contributions and related work

The user supplied the original implementation brief from a piker agent.
This OpenCode revision bounds eligibility and makes same-tree
completion, operation-specific check history, author preservation,
message selection, prompt defaults and minimal recovery ownership
explicit. It does not mark any existing Taken task accepted.

- Shipped baseline: https://github.com/baudco/ai.skillz/pull/24
- Deferred comparison: https://github.com/baudco/ai.skillz/pull/25
- Existing pending-tail revision work remains separate from rewriting
  an already-created commit; coordinate shared primitives without
  treating these as interchangeable operations.
