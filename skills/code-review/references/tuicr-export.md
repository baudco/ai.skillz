# Local Tuicr Finding Export And Injection

Use this reference when the user explicitly requests Tuicr payloads or
adding this review's findings as local drafts. A payload export is not
an injection, and neither action publishes a forge review.

For explicit requests to copy existing remediation responses into
another native view, use
[tuicr-mirror.md](../../code-review-changes/references/tuicr-mirror.md).
Response mirrors preserve source lineage and require a verified
destination text/anchor projection; do not export them as new findings.

## Prepare The Handoff

Resolve the user's executable, wrapper environment, and native session
using sections 1 and 2 of
[`tuicr-local.md`](../../code-review-changes/references/tuicr-local.md).
Reuse its persisted-anchor verification rules. Do not run its source-fix
workflow or treat new findings as responses to existing parent comments.

Inspect the installed `review --help` and payload contract before export.
The currently verified CLI offers only `list`, `add`, and `comments`;
there is no session-create or batch-import command. Do not invent either.
Use one supported `review add --input @FILE` payload per finding beneath
the ignored `.ai/code-review/reports/` directory, only after an export
request. This is Tuicr input, not `review-result-v1.schema.json` output.

Each payload supplies `comment_type`, explicit agent `username`, full
`content`, and a `target` of type `review`, `file`, `line`, or
`line_range`. Inline targets include `file`, explicit `side`, and either
`line` or `start_line`/`end_line`. Keep a single-line target distinct from
an explicit range. Use `none` unless the user's configuration establishes
a custom type; carry severity and confidence in the body. Tuicr trims
content, so prepare bodies without leading or trailing whitespace and
verify the entire resulting body, not a title or substring.

Include the full reviewed head, requested base, exact range, and relevant
evidence in each finding body. The CLI leaves `commit_id` null; prose
identity is provenance, not a substitute for verifying the session.
Keep forge/provider metadata separate from local Git scope and do not
infer a forge session from a related PR number.

The export README and final handoff must state:

- **Prepared only** or **persisted additions verified**, including counts
  and any partial completion; never call payload preparation injection.
- The canonical checkout, full scope OIDs, resolved command/environment,
  and verified session path/slug, or the exact missing-session blocker.
- Which payloads remain pending and which returned IDs are verified.
- That persisted additions do not by themselves prove TUI visibility.

## Obtain A Native Session

If the same-environment listing has no matching session, ask the user to
open the exact target in their normal TUI and keep it open until initial
comments are added. Native Tuicr persists an ephemeral session when the
review target becomes active, then removes it on normal exit if it has
neither comments nor reviewed state. Opening and immediately exiting an
empty review therefore does not provide a durable injection target.
Never mark files reviewed to keep a session alive or synthesize session
JSON, IDs, manifests, or storage paths.

A request to export or inject does not silently authorize launching an
interactive UI, a wrapper build, or PTY automation. If the user explicitly
authorizes native UI initialization, use that native selection flow and
verify the resulting session through the supported CLI. Fixed sleeps and
blind keystrokes from a one-off PTY run are not a portable procedure.
Without such authorization or a usable session, report the blocker and
the user opening step; leave payloads prepared only.

## Add Only After Authorization And Complete Preflight

Require a current-prompt request to add these local draft findings.
Before the first addition, preflight the entire batch: session identity,
all supported payload fields, original paths/sides/structural ranges,
explicit authors, full bodies, and uniqueness of intended comments.
Snapshot every file's `reviewed` and `reviewed_hunks` values and retain
existing comments for comparison. Do not change these user-owned markers.
If any target is unsupported or ambiguous, add nothing and report it.

Before each addition, refresh `review comments` and persisted JSON using
the same wrapper prefix and absolute session path. Match an earlier
addition only by exact full body, explicit author, and complete anchor
(target kind, path, side, storage key, and structural range), plus type
and null `commit_id`. One exact match can be reused; multiple matches or
conflicting identity are blockers. Do not use title, order, or counts as
identity, and do not add a duplicate after uncertain command completion.

Add sequentially with the supported `review add --session SESSION
--repo CHECKOUT --input @FILE` interface and safe argv boundaries. After
each add, capture its returned ID, refresh both CLI comments and persisted
JSON, and verify exactly one matching ID, full body, author, type, side,
and anchor. Range comments live at `line_comments[end_line]`, not
`line_comments[start_line]`; verify `line_range: {start, end}` separately.
Ordinary single-line comments have `line_range: null`. A lookup at the
wrong key is a verification defect, not permission to retry the add.
Compare every file's reviewed/hunk values after each addition, and
revalidate session identity before proceeding to the next payload.

Stop on the first command failure, verification ambiguity, identity drift,
or reviewed-state mismatch. Preserve the snapshot and successful IDs;
report partial completion without deleting comments or reverting human
state. On retry, reconcile persisted full identities before any mutation.

Finally refresh `review list`, `review comments`, and persisted JSON.
Verify the complete intended batch and every file/hunk reviewed value
against the initial snapshot. Report additions as persisted local drafts,
not resolved feedback or review acceptance. `active: true` is only a
persisted activity marker; live-process, polling, merge, and visibility
claims require separate evidence.

## Implementation Evidence And Version Boundaries

These rules were checked against Tuicr's installed CLI and source on
2026-10-07: `src/review_store.rs` (`add_comment_to_session`),
`src/model/review.rs` (`ReviewSession`/`FileReview`),
`src/model/comment.rs` (`Comment`/`LineRange`),
`src/persistence/storage.rs` (data root and empty-session deletion),
`src/app/session.rs` (native persistence and commit-range identity), and
`src/vcs/git/cli.rs` (range ordering). Recheck the installed contract when
versions or backends differ; these are source-relative evidence paths,
not machine-local executable or consumer-storage defaults.

The historical validation used an explicitly authorized native PTY/TUI
selection of all 20 commits, kept open during supported CLI additions.
It verified seven complete comments, zero reviewed files, and unchanged
file/hunk markers. This is lifecycle evidence, not a generic PTY helper
or authorization to reproduce sessions in another consumer.
