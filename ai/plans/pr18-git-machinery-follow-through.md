---
created_at: 2026-10-08T00:00:19Z
generated_by:
  harness: opencode
  provider: openai
  model: gpt-6.1-sol
---

# PR #18 follow-through: reusable Git machinery

## Evidence and ownership

This document preserves the Git-extraction diagnosis requested after
the PR #18 review. The authoritative bounded handoff is the task in
Taken source `ai.skillz`, ID
`f489d534-83e1-4627-9f89-d700f374dd48`, in the
[local store](../../.taken/current.org). Read that task's complete
subtree and prerequisites before acting. This document is technical
evidence, not a second work queue or implementation acceptance.

Assessment snapshots:

- Shared source: `a44187d2adf4bf20bbdf4af53a23cf8ee402fe48` on
  `store_native_handoffs`.
- PR #18 checkout: `9f10391eeac8b73d4896ec17c8579faed65ea295` on
  `pyskillz`.
- Local assessment only: no files changed or tests executed during
  the original diagnosis. Re-resolve current source versions before
  implementing; the federation checkout is the document/store home.

Related work:

- https://github.com/baudco/ai.skillz/pull/18
- https://github.com/baudco/ai.skillz/pull/24
- https://github.com/baudco/ai.skillz/pull/25

## Conclusion

There is a useful reusable Git toolkit inside commit-plan. The
strongest extraction candidates are checkout inspection, raw object
inspection, private-index operations and later guarded publication.
Put Git mechanisms in `aiskillz`; keep commit-plan's boundary,
authorization, review, completion and recovery decisions in the skill.

Agents and human-driven tools should consume structured observations
and narrowly defined operations without depending on a commit-plan
specification or a harness's terminal output.

## Git subprocess handling

Parallel wrappers exist in the builder, executor, isolated-check
runner and package discovery layer. They repeat process invocation,
environment construction, output decoding and result handling.
Their policies differ legitimately:

- Discovery strips ambient Git overrides, tolerates unavailable
  paths and uses a short timeout.
- Planning rejects ambient redirection, suppresses hooks/fsmonitor,
  retains conversion configuration and captures exact bytes.
- Execution rejects redirection, retains intended editor/hooks and
  reports actionable failures.
- Isolated checks use an explicitly selected environment and
  independent metadata, then verify the result.

Consolidate low-level invocation behind explicit policies, with
structured results and deliberate bytes/text handling. Preserve the
discovery wrapper's unavailable result where required. Execution must
retain the underlying error. Interactive editor execution must not
inherit discovery's two-second timeout or captured-output behavior.

Do not silently strip `GIT_INDEX_FILE` in the execution path. That
would weaken the executor's explicit refusal of ambient redirection.
Do not turn this extraction into a permissive arbitrary-Git CLI.

Starting points: `skills/commit-plan/scripts/plan-build.py`,
`skills/commit-plan/scripts/plan-exec.py`, and
`aiskillz/git/_commands.py`.

## Checkout identity and observations

Commit-plan independently resolves and validates the checkout root,
private Git directory, common directory, branch and HEAD. Package
discovery already resolves much of this, and the shared-source
snapshot adds a short branch observation.

Introduce a structured checkout observation covering root, private
and common Git directories, full branch ref, HEAD OID, object format
and detached/unborn/bare status where applicable. Include registered
worktree information without treating an observation as a lock.

Separate inspection from matching recorded expectations. A discovered
branch does not authorize using it. Keep the short display name
distinct from the full `refs/heads/...` publication identity.

Preserve existing package contracts: `repository()` intentionally
returns live linked checkouts and excludes the main checkout. Richer
inspection can support that interface without changing its meaning.

Starting points: `aiskillz/git/_discovery.py` and
`plan-exec.validate_identity()`.

## Raw object and commit inspection

The executor validates full canonical SHA-1/SHA-256 OIDs and object
types, then reads raw commits without replacement/graft semantics.
This is useful for general Git management and amendment support.

`raw_commit_parent_tree()` currently combines parsing with the
single-parent restriction required by ordinary plan completion.
Extract a reader which returns every parent and the tree. Let the
caller impose eligibility. Root and merge commits must remain
representable even when amendment or completion policy rejects them.
Raw author/message evidence can later support exact author-preserving
amendment without treating edited message text as a completion key.

Keep object-ID validation separate from user-supplied ref/revision
resolution. Option-shaped input must not reach Git as a canonical OID.

Repeated `cat-file -t` calls offer a concrete batching opportunity.
A batch object-inspection API can validate exact OIDs/types with fewer
subprocesses. Do not cache mutable HEAD/index observations across
review or publication, or assume a persistent cache proves freshness.

Starting points: `plan-exec.validate_objects()`,
`plan-exec.raw_commit_parent_tree()` and `plan-exec.classify()`.

## Private indexes and disposable repositories

The builder snapshots index bytes/filesystem metadata and creates
private indexes. The executor separately validates index files,
compares staged trees and publishes patches under `index.lock`.
Reusable mechanisms include locating/safely reading the index,
absent-index handling, private-index cleanup, literal file selection,
patch materialization and exact-tree comparison.

Keep selection, authentication, unrelated staged-work refusal and
the authorized transition in commit-plan. An isolated planning index
preserves real staging and refs/history; materializing Git objects is
still an intentional local object-database effect.

Retain two distinct disposable-checkout contracts:

- Independent temporary repository for exact-tree project checks.
- Owned detached worktree for editor/hooks to create a candidate
  commit before live branch publication.

Their metadata isolation and lifecycle effects differ. Check
selection, import-probe policy, prior-PASS evidence and interactive
review remain workflow responsibilities.

Starting points: `plan-build.snapshot()`,
`plan-build.private_index()`, `plan-exec.validate_index_file()`,
`plan-exec.index_matches()`, `plan-exec.stage_under_lock()`,
`plan-exec.isolated_tree()` and `plan-exec.commit_checkout()`.

## Guarded publication and superficial duplication

Expected-old-OID ref publication, symbolic-HEAD protection and index
protection are useful later extraction candidates. The existing
functions also contain plan-specific progress/recovery decisions;
exporting those assumptions wholesale would couple other operations
to append-only commit-plan behavior.

A general publication mechanism needs an explicit ref, expected old
OID and new OID. Its caller owns authorization, review, eligibility
and recovery. Preserve retained evidence on races and failures. Do
not claim a transaction spanning refs, index and external actions.

Immutable artifact publication is another real overlap: the builder
and WKT preview writer use temporary files, hashes and exclusive hard
links. A small lower-level artifact module may serve both. Preserve
their different existing-file policies and domain JSON encodings;
changing canonicalization changes pinned digests.

Git index/HEAD lockfiles and dialog `write.guard` have different
protocols. Similar `try/finally` code alone does not justify a generic
lock, journal or workflow-state framework.

Starting points: `plan-exec.protected_index()`,
`plan-exec.protected_branch()`, `plan-exec.execute()`,
`plan-build.store()`, `wkt.save_wkt_preview()` and
`wkt._relations.update()`.

## Proposed package boundary and user workflow

Proposed responsibilities within `aiskillz.git`:

- Process: explicit environment policy, invocation and results.
- Checkout: layout, registered worktrees and observations.
- Objects: canonical IDs, types and raw commit/object inspection.
- Index: snapshots, private indexes and exact-tree comparisons.
- Refs: narrowly guarded publication after concrete reuse exists.

These modules must not import harness readers, Taken property
parsers, CLI presentation or commit-plan schemas. Preserve a package
import path with no store scans, process launch or configuration
mutation merely from importing Git primitives.

A proposed read-only `ai.git` inspection command could expose JSON
checkout identity, branch/HEAD, staged/unstaged state and worktrees.
The same Python records can support a Taken/modden adapter validating
an explicitly selected checkout. Neither is an existing interface.
Task identity, logical workspace and observed Git state remain
different records with different owners.

## Deployment gate and extraction order

Commit-plan currently imports its adjacent executor and works from
linked source deployments without an installed package. Before moving
helpers, define package resolution from the same canonical source
checkout. A bare import must not choose an older installed aiskillz.
Preserve entrypoints, pinned spec/artifact semantics and native
Xonsh rendering. Apply repository license/header conventions to
extracted modules while preserving ownership.

Recommended order:

1. Establish source-import/version selection.
2. Extract checkout observations and raw object inspection.
3. Consolidate subprocess mechanics with explicit caller policies.
4. Extract private-index and disposable-checkout primitives.
5. Consider guarded publication when a second workflow needs it.

Use existing Git-layout and commit-plan behavioral suites after each
slice, plus focused environment, raw-history, unusual-path, index and
deployment-import cases. Include unrelated cwd, linked/submodule
deployments, absent installation and conflicting installed versions.
Use real Git behavior rather than mocked argv as the only evidence.

This is bounded #18 follow-through, starting with read-only primitives.
Amendment, pending-tail revision and production Taken/modden launch
remain owned by their existing tasks. Passing checks or finishing an
extraction does not change those tasks' acceptance states.
