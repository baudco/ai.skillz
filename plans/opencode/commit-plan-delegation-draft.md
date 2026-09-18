# Commit Plan Delegation And Worker Lifecycle

Draft for human review. This does not change deployed skills,
permissions, defaults, or Git history.

## Suite-Wide Default

Make deployed skills worker-compatible by default: explicit inputs,
ownership, outputs, authorization, and a usable worker-context entry
point. Delegate substantial bounded tasks by default when supported,
with the parent remaining the human liaison. `/commit-plan` is the
first application, not a special architecture confined to one skill.

Worker compatibility does not require spawning a process for every
composed skill. Dependencies such as formatting conventions and
small read-only helpers run inside the owning worker. Never recurse
through the delegation rule merely because one skill loads another.
Keep human approval/clarification delivery with the parent; preserve
required terminal/editor interaction when a harness cannot delegate
it correctly. Explicit inline requests and unavailable delegation
remain supported. Exceptions must be documented by capability or
workflow constraint rather than introduced silently per harness.

Review these defaults before changing deployment instructions across
the suite. Harness adapters report blocking/background capabilities;
they do not manufacture concurrency by labelling a call a subagent.

## Proposed Canonical Instruction

Delegate the complete `/commit-plan` workflow to one dedicated
planning worker when the harness supports delegation. Honor an
explicit request for inline execution. If delegation is unavailable,
run inline and describe that limitation briefly. A planning worker
already executing this workflow must not delegate it recursively.

Delegation and background execution are separate capabilities.
Claim continued parent responsiveness only when the adapter supports
and has demonstrated it. Otherwise describe the call as delegated
but blocking. A headless subprocess is not automatically a background
agent with durable conversation or approval handling.

The parent supplies the exact canonical worktree, requested scope,
boundaries and exclusions, repository guidance, verification evidence,
shell preference, and authorization constraints. Reuse previously
resolved guidance with its paths and identities; do not repeat source
discovery merely because a worker owns the task. The worker validates
applicability and freshness before relying on supplied evidence.

The worker owns its plan artifacts. The parent does not generate
competing messages or stage changes for that task. Different planning
tasks need separate artifact namespaces. Preserve the real index and
worktree under the current planner contract. Delegation does not fix
the existing unrelated-staging limitation or relax its refusal.

The worker returns the complete native handoff, artifact pins, scope,
verification outcomes, exclusions, and unresolved questions. The
parent reports them inline, without substituting a link-only response
or rerunning the planning workflow. If discussion changed the relevant
repository state, validate freshness before calling the plan ready.

Delegation grants no additional commit, edit, publication, network,
or filesystem authority. A parent prompt cannot manufacture tool
permissions. Record which policy is actually inherited or configured.
No automatic commit behavior is introduced by this proposal.

## Cross-Harness Reference Contract

All human-facing repository locations use verified editor-jumpable
`path:line` references under the canonical `code-nav-refs` contract.
Use absolute paths for other worktrees. Line numbers refer to the
current file, not a stale pre-edit snapshot. Drafts and generated
handoff documents are included; shell arguments remain literal paths.

Deploy the same short mandatory rule through each harness's loaded
instruction layer, and include it in delegated-worker handoffs. Skill
discovery alone is not a guarantee that the formatting skill loads.
Add shared fixture tests for parent and worker responses across
providers. Where an output interception hook exists, validate and
request correction before delivery; where absent, retain an explicit
final-answer check and report the enforcement limitation.

A reference validator must distinguish prose citations from runnable
commands, URLs, branch names, and hypothetical paths. Syntactic
`path:line` validity alone does not prove relevance or current line
accuracy. Verify local targets when access exists, using the correct
worktree root. This is a proposed enforcement layer, not an installed
cross-harness output gate.

## Lifecycle And Human Intervention

Suggested task states are internal runtime metadata, not transitions
in human-owned Org/Markdown checklists:

`queued -> running -> ready -> delivered`

Additional outcomes: `waiting_for_human`, `stale`, `failed`, and
`cancelled`. Transport/process loss must distinguish an unknown
outcome from a confirmed cancellation or successful completion.

Every request has a stable task ID and revision. Updates and results
identify both, so a late result cannot replace a newer scoped request.
Record artifact ownership and at most one active owner per revision.
Do not promise exactly-once process execution; use task identity and
idempotent delivery to prevent duplicate handoffs.

Borrow Firstmate's distinction between a result being durably stored,
displayed to the human, and processed by the parent. Acknowledgements
identify the task revision and result sequence. A wake notification
is a hint to reconcile durable state, not authoritative completion.
Keep steering separate from interrupt, exit, relaunch, and worktree
teardown. Sending an interrupt is not confirmed cancellation.

- New unrelated discussion does not cancel or pause the worker.
- Relevant discussion without a scope change may supply context,
  but must not silently rewrite an in-flight task specification.
- A scope amendment requires acknowledgement from the worker or an
  explicitly superseding revision. Quarantine results from the old
  revision instead of silently presenting them as current.
- A worker question or review escalation becomes `waiting_for_human`.
  The parent preserves and surfaces the exact question and evidence.
- Human pause requests stop work at a supported safe boundary.
  Process suspension is not a transaction-safe workflow pause.
- Resume requires an explicit decision and revalidation of relevant
  repository state, evidence, and authorization. Silence is not consent.
- Cancellation is acknowledged and bounded. Preserve completed
  evidence and report whether cleanup and worker exit are confirmed.
  Never remove user work or another task's files during cleanup.
- Failure records the last confirmed phase and retained artifacts;
  it must not disappear merely because the parent changed topics.

Future auto-mode must make human-requested pauses and review-agent
escalations first class before subsequent commits. Such execution
requires its own strict authorization and recovery contract; this
planning-only draft does not implement or authorize it.

## Optional Trio / Tractor Supervisor Experiment

Start with a small out-of-process supervisor and fake workers. Let
the root harness communicate with that supervisor instead of assuming
the interactive harness can embed a Trio event loop or own nurseries.
If an in-process integration is supported, evaluate it separately.

Use Trio structured concurrency to own subprocess lifetimes, stream
readers, bounded channels, and cancellation. Introduce Tractor actors
when actor isolation, supervised PTY access, or cancel-and-respawn
through `tractor.Context` semantics warrants it. PTYs alone do not
require Tractor; choose actors for ownership/isolation benefits.
See `multi-harness-supervisor-draft.md` for the external-supervisor
pilot and pinned Firstmate/no-mistakes research.

One adapter per harness supplies launch arguments, capabilities,
structured events, result extraction, and approval routing. A worker
request contains ID/revision, working directory, task payload,
declared environment/model configuration, artifact destination, and
the effective authorization scope. Capabilities include native task
delegation, nonblocking operation, streamed events, continuation,
cooperative pause/cancel, approval interaction, and durable results.
Mark unsupported or unverified capabilities explicitly.

A daemon service lifetime and a task lifetime are distinct. Keep the
supervisor attached to a deliberate service owner; do not orphan
workers through double-fork daemonization. Drain stdout/stderr with
bounded storage and backpressure. Send cancellation through the
supported API first; any signal escalation must target only owned
processes and follow the agreed shutdown policy.

Structured concurrency does not provide persistence across root
process failure. Test disconnect/reconnect and outcome reconciliation
explicitly. Treat capability passing, process termination, and Git
transaction integrity as separate concerns.

## Acceptance And Measurement

Measure three independent outcomes:

1. Request to accepted plan delivery.
2. Parent response latency while a plan is running.
3. Correct completion after unrelated discussion, relevant updates,
   human questions, explicit amendments, pause, or cancellation.

Test lifecycle behavior with deterministic fake workers first. Then
use a disposable repository and a real planning worker: introduce an
unrelated parent message, a selected-file edit, and a human decision
request in separate trials. Check result identity, drift refusal,
no duplicate delivery, preserved work, and confirmed worker shutdown.
Do not execute generated commits merely to test planning concurrency.

Compare native harness delegation with supervised headless workers
separately. Where possible, control model and reasoning settings;
otherwise label the experiment as a native-workflow comparison.
Record process spawn, request submission, first event/token, tool
intervals, final artifact, completion event, and parent delivery.
These intervals do not reveal server queue time unless telemetry
actually exposes it. Avoid unsupported causal latency claims.

## Intended Order After Stack Cleanup

Review this contract, then implement the smallest native delegation
path for supported harnesses with a documented inline fallback.
Run the interruption/responsiveness test before expanding adapters.
Use the supervisor fake-worker spike to validate lifecycle semantics
before invoking real headless harnesses. Inspect pi's actual API and
deployment surface before promising support or adding an adapter.
