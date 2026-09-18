# External Multi-Harness Supervisor Draft

Review draft, not an implementation or permission grant. Start after
the executable commit-plan stack is settled. Leave deferred virtual
index work separate; first solve worker ownership, human interaction,
and parent responsiveness without changing commit authorization.

## Initial Shape

```text
interactive root harness
    <-> UDS task/event interface
Trio supervisor service
    +-- task nursery: headless worker + output readers
    +-- task nursery: headless worker + output readers
    +-- durable task/result records + approval routing
```

The interactive root submits tasks and remains the human's liaison.
The external supervisor owns worker subprocesses, not conversation
turns. Its service lifetime and each task lifetime are explicit.
Use UDS for the local root-to-supervisor control plane. Keep worker
stdio pipes or PTYs as a separate adapter concern; these transports
serve different interfaces. Do not require a PTY for workers that
provide a useful headless event stream.

Add Tractor when actor isolation, remote placement, supervised PTY
hooks, or cancel-and-respawn with `tractor.Context` semantics becomes
useful. A PTY is not itself an actor requirement. Cancellation must
cover the actual subprocess and stream readers, not only an RPC wait.
Restart creates a new attempt with a durable brief; it does not imply
restoration of an arbitrary harness conversation.

## Transport And Debugger Choice

Keep the task protocol independent of its socket address: explicit
message framing/version, request and attempt IDs, result sequences,
acknowledgements, and bounded payloads. A future TCP/multiaddr endpoint
can retain this contract, but remote identity, authorization, reconnect
and failure semantics require explicit work. UDS peer credentials do
not themselves define the application's authorization policy.

Tractor's inspected revision is
`0c52f2770a02987b62fb7ac51164c7fef4482d4c`. It already documents
TCP/UDS and `/unix/`, `/ip4/` and `/ip6/` multiaddr forms. Evaluate
its public advanced `tractor.Channel` API versus actor contexts and
`MsgStream` before importing private IPC helpers into plain Trio.
If private helpers are deliberately used, isolate that dependency in
a small pinned adapter rather than spread it across harness code.

`debug_mode=True` can help debug the Tractor supervisor and Python
wrappers with coordinated debugger terminal ownership. It does not
instrument arbitrary external harness CLIs. Keep debugger terminal
ownership separate from any worker PTY and test interactive use under
concurrent streams before relying on it for production diagnosis.

[Tractor IPC API](https://github.com/goodboy/tractor/blob/0c52f2770a02987b62fb7ac51164c7fef4482d4c/docs/api/ipc.rst)
[Tractor multiaddr implementation](https://github.com/goodboy/tractor/blob/0c52f2770a02987b62fb7ac51164c7fef4482d4c/tractor/discovery/_multiaddr.py)
[Tractor debugging](https://github.com/goodboy/tractor/blob/0c52f2770a02987b62fb7ac51164c7fef4482d4c/docs/guide/debugging.rst)

Managed contexts and streams can supply error propagation and bounded
producer/consumer behavior. An external CLI still needs an adapter
mapping exit codes, structured errors, EOF, stream overrun, and child
cleanup into those semantics. A nursery exit can prove that owned
reader tasks and awaited processes finished; it cannot automatically
account for daemonized or escaped descendants. Distinguish accepted
results, cooperative cancellation acknowledgement, and reaped workers.

## First Pilot

Use deterministic fake workers before real harness adapters. Exercise
start, concurrent progress, result persistence, approval requests,
human pauses, cancellation, replacement, and root disconnects. Prove
that a new conversation topic does not cancel unrelated owned work.
Keep output bounded and drain streams without blocking the root UI.

Requests carry task ID/revision, attempt ID, canonical worktree,
scope, supplied context/evidence, artifact destination, explicit
environment/model configuration, and effective authorization policy.
One active mutation/artifact owner per task revision; reject stale
attempt results after replacement. Do not promise exactly-once runs.

Result lifecycle is separate from worker lifecycle: stored, displayed,
and processed are distinct acknowledgements. Record outcomes before
sending wake events, then reconcile durable records on wake/reconnect.
An unrelated reply is not acknowledgement or human acceptance.

Steering, cooperative pause, interrupt, exit, relaunch, and teardown
are different operations. Report requested/sent/acknowledged/quiescent
states accurately. A lost transport has an unknown outcome until
reconciliation; a client timeout is not necessarily worker failure.
Human questions pause dependent work at a safe boundary. Resume only
after a decision and relevant state/authorization revalidation.

Do not inherit broad permission bypass merely to suppress prompts.
An adapter reports its real capabilities and policy inheritance.
Explicitly support unavailable pause/resume or approval interaction
rather than simulate successful control. No commits or forge
publication are enabled by the planning-only pilot.

## Research Snapshots

Read-only source inspection through GitHub API, not runtime validation:

- Firstmate: `f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b`.
- No-mistakes: `71cd9110543eeac67fd76180f2bdabd355395ec2`.

Both repositories have MIT licenses, copyright 2026 Kun Chen.
If extracting substantial code, retain license notices and source
provenance. This does not establish dependency/harness licenses.

### Firstmate

The single-liaison model is backed by external interactive harness
sessions, normally in detached terminal windows with separate Git
worktrees. It is not simply native subagent delegation or a generic
headless process pool. A Claude hook discourages native delegation
from the primary; this is harness-specific enforcement.

Pi also has an in-process supervision session using createAgentSession
to watch the external crew. Its synchronous-subprocess responsiveness
lessons are relevant, but that Pi integration is not required for our
external Trio supervisor.

Adopt the contracts first: sequenced steering inboxes, explicit worker
acknowledgement, durable results before notification, stored/displayed/
processed distinctions, and separation of lifecycle control from
teardown. It documents unconfirmed interrupts instead of equating
terminal input with cancellation. Do not adopt permission-bypass
launch defaults or terminal polling without evaluating alternatives.

In the inspected interrupt implementation, all adapters except Muse
have no cancellation acknowledgement source, so successful key
delivery yields `cancel=unconfirmed`. Muse captures the active run ID
first and polls for that run's terminal `cancelled` record; timeout or
a different outcome remains unconfirmed. Exit waits for backend `dead`
classification, whose process coverage varies by adapter. This is
supervision with explicit uncertainty, not a process-tree join or
Trio-style structured lifetime guarantee for every external tool.

No `intercom` interface was identified in the inspected Firstmate Pi
sources. The separately supplied pi-intercom extension is examined
under Additional Pi Ecosystem References below.

It supports local-only and direct-PR delivery in addition to its
no-mistakes integration. Local-only branch delivery is not our
authenticated private-index/exact-tree commit protocol.

[Firstmate architecture](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/README.md#L27-L53)
[Control semantics](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/docs/agent-control.md#L3-L106)
[Interrupt acknowledgement implementation](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/bin/fm-control.sh#L354-L509)
[Outcome acknowledgements](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/bin/fm-branch-outcome.sh#L18-L58)
[Pi responsiveness](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/docs/pi-supervision-branch.md#L69-L120)
[Launch defaults](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/bin/fm-spawn.sh#L1655-L1717)
[MIT license](https://github.com/kunchenguid/firstmate/blob/f5d7f5f2484564dd855b76e7e40ef8c40dc7ab2b/LICENSE#L1-L21)

### No-mistakes

This is a daemon-owned Git delivery pipeline with a local Git proxy
and disposable worktree, rather than just a review prompt. Its order:

`intent -> rebase -> review -> test -> document -> lint -> push -> pr -> ci`

It supports several forges, not only GitHub. Some publication steps
can skip, but local mode still works on committed branch history;
dirty worktrees and default-branch submissions are rejected. Earlier
fix/rebase phases can create commits. Do not treat it as a drop-in
offline private-index workflow or adopt its sequencing wholesale.

Borrow explicit approve/fix/skip gates, fresh review rounds separated
from fixer sessions, coverage tied to trusted changed paths, and
durable step/finding records. Client waiting timeouts differ from
pipeline failure; reattachment queries existing runs. Confirmed
quiescence before reporting abort is relevant to our cancellation
contract. Unpublished correction commits need explicit custody.

Default review auto-fix rounds are zero; several other phases default
to three. `--yes` expands consent for ask-user findings. Our human
intervention and future auto-mode policies remain separate decisions.

[Pipeline overview](https://github.com/kunchenguid/no-mistakes/blob/71cd9110543eeac67fd76180f2bdabd355395ec2/README.md#L37-L68)
[Review iterations](https://github.com/kunchenguid/no-mistakes/blob/71cd9110543eeac67fd76180f2bdabd355395ec2/docs/src/content/docs/reference/pipeline-steps.md#L86-L137)
[Pause and reattachment](https://github.com/kunchenguid/no-mistakes/blob/71cd9110543eeac67fd76180f2bdabd355395ec2/docs/src/content/docs/reference/cli.md#L114-L240)
[Forge selection](https://github.com/kunchenguid/no-mistakes/blob/71cd9110543eeac67fd76180f2bdabd355395ec2/internal/pipeline/steps/host.go#L44-L175)
[MIT license](https://github.com/kunchenguid/no-mistakes/blob/71cd9110543eeac67fd76180f2bdabd355395ec2/LICENSE#L1-L21)

## Additional Pi Ecosystem References

Read-only source snapshots, not installed or runtime-validated:

### pi-intercom

Snapshot `199279ae861bf53ce014809fb2a03337538ae13e`, MIT.
Same-machine broker using Unix-domain sockets, Windows named pipes,
and an opt-in Windows loopback-TCP path. Four-byte-length-prefixed
JSON carries IDs, correlation, sequences, receipts, and lifecycle
metadata. Endpoint epochs and separate questions/progress channels
are useful patterns. Reconnect mailbox retention is bounded and
in-memory; some history/records persist separately. Receipt or prompt
injection does not prove task completion, and timeout is not cancel.
Socket writes do not await backpressure in the inspected broker.

[Protocol and usage](https://github.com/nicobailon/pi-intercom/blob/199279ae861bf53ce014809fb2a03337538ae13e/README.md)
[Broker implementation](https://github.com/nicobailon/pi-intercom/blob/199279ae861bf53ce014809fb2a03337538ae13e/broker/broker.ts)

### pi-subagents

Snapshot `f4918e80b531f1bf9f1d9e847b8f86c9016108f1`, MIT.
Foreground dispatch uses in-process sessions; background work uses
a detached runner. External CLI runners are a separate path. Public
delegation/preflight APIs, budgets, transcript artifacts, and explicit
unknown-cleanup outcomes are useful. Transcript forking and tool
ceilings are not process/filesystem isolation. Owned process-group
cleanup does not prove cancellation of escaped descendants; detached
work can outlive its parent and lose the completion notification.

[Delegation architecture](https://github.com/nicobailon/pi-subagents/blob/f4918e80b531f1bf9f1d9e847b8f86c9016108f1/README.md)
[Extension API](https://github.com/nicobailon/pi-subagents/blob/f4918e80b531f1bf9f1d9e847b8f86c9016108f1/docs/extension-api.md)

### oh-my-pi

Snapshot `78b753124d11f8dd3ae73e2524125890ff7c977e`, root MIT;
retain any component-specific notices. Integrated Pi fork with Bun
and native components, built-in delegation, SDK sessions, stdio RPC,
ACP, and lifecycle events. Result acceptance can precede cleanup;
keep these states distinct in our protocol too. Similar SDK shapes
do not establish compatibility with upstream Pi extension packages.
Evaluate a connector rather than adopt an entire harness distribution
as the supervisor's dependency.

[Integrated harness](https://github.com/can1357/oh-my-pi/blob/78b753124d11f8dd3ae73e2524125890ff7c977e/README.md)
[Task executor](https://github.com/can1357/oh-my-pi/blob/78b753124d11f8dd3ae73e2524125890ff7c977e/packages/coding-agent/src/task/executor.ts)

## Measurement And Delivery Gate

Compare native delegation and supervised headless execution separately.
Record parent responsiveness, interruption correctness, and time to
accepted plan. Control model/settings where possible; retain native
workflow comparisons where not. Attribute queue/provider/harness time
only where events support the distinction.

First real-harness trial uses one disposable planning task, unrelated
parent conversation, and a deliberate human question. No returned
commit sequence is executed. Require durable result delivery, no lost
question, no false cancellation confirmation, and preserved Git state.
Expand to more harnesses only after this lifecycle gate is reviewed.
Neither researched project becomes a dependency by this draft.

## Describing The Guarantees

Prefer "concurrency-aware Git workflows" and explicit properties:
private-index planning, pinned boundary trees, drift detection, and
owned task lifetimes. The supervision pilot targets structured
concurrency; do not label the current CLI planner an SC runtime.
Neither design yet guarantees arbitrary concurrent shared-worktree
edits, unrelated staging reconciliation, or complete transactionality
across commit/hooks/index recovery. Describe supported coordination
and fail-closed cases rather than promising blanket concurrency safety.
