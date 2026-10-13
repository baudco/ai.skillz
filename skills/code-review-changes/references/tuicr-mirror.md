# Responses In Staged And Unstaged Tuicr Views

Use this workflow for local `-r`/`--respond` remediation replies. The
normal handoff puts a reply at the original comment and a verified copy
beside the corresponding unstaged adjustment, so the human can inspect
the new code before staging. Mirroring remains optional and scoped:

- `-r`: add source replies and mirror the eligible, uniquely mapped
  adjustment replies; disclose omitted mappings and missing views.
- `-r --no-mirror`: add replies only in the selected source session.
- `-r --mirror`: require all eligible adjustment replies to have a
  verified destination before any mirror additions. A missing native
  view or ambiguous mapping leaves the mirror batch pending; never
  claim that a source-only result satisfied this stricter request.

These are skill options, not invented flags for the native Tuicr CLI.
Recognize one policy option only in the trusted invocation envelope
after response authority and before the session header. Do not scan
comment bodies for flags. No response authority means no reply additions;
carrying human notes has its own explicit authorization below.
Do not create another worktree, stage source, alter review markers,
copy into every checkout session, or publish a forge review.

Eligible means a response concerns a source path changed by this review
and has a supported inline anchor that uniquely refers to an actual
adjustment hunk. An unchanged acknowledged finding or file-level reply
does not justify inventing an inline target. Preflight and declare the
eligible subset and omissions before writing. Default best-effort
selection is not permission to write an ambiguous subset or disregard
identity/review-state failures during addition. `--mirror` applies its
all-or-nothing gate to the complete eligible batch.

## Select Both Native Sessions

Use the executable/environment resolution and supported CLI from
[tuicr-local.md](tuicr-local.md). List sessions in that same environment
and select the exact source and destination by canonical repository,
branch/HEAD, local kind, and persisted diff mode. A combined session is
not a substitute for an explicitly requested unstaged session.

Normally select the unique local unstaged view for the receiving
checkout. If it does not exist, request its native opening step and
report mirror preparation separately from completed source replies.
If the source already is that unstaged session, do not duplicate every
reply inside the same view and call it a second-session mirror. Report
the lack of a distinct native destination and verify the ordinary reply
anchors independently; the exact bridge below does not apply by fiat.

Verify the original responses already exist before adding anything.
Preserve their IDs, full bodies, authors, types, parent-ID markers,
sides, storage keys, and structural ranges. Copies are independent
comments in another view, not threaded replies or newly written human
feedback. Their parent IDs refer to the original source session and
need not occur in the destination; retain that external lineage.

If the destination is missing, follow the missing-native-session rules.
The human opens the exact view and keeps an empty session open until
comments are added. Exporting payloads or requesting mirrors does not
authorize silently launching a TUI or fabricating session JSON.

## Prove The Source Text And Destination Hunks

Capture the real index bytes, stage/debug metadata and selected paths,
HEAD/branch, source/index/worktree blobs, original comments, and every
file's reviewed/hunk markers. Use read-only Git operations; if a tree
must be materialized, use a private index rather than writing the real
index. Verify both native sessions' saved diff-content hashes against
their corresponding current diffs using the installed backend's hash
and diff-generation contract. A matching HEAD or filename is not
enough, and current index text does not establish an old session's
staged snapshot identity.

The exact bridge for this common review flow is:

**staged NEW text = index text = unstaged OLD text**

The source staged snapshot's NEW-side blob must equal the destination
unstaged snapshot's OLD-side blob for each selected path. Under that
proof, a NEW-side source response at line N can be copied to OLD-side
line N in the unstaged session. Preserve single-line versus explicit
range shape and both range bounds. The original staged response stays
at its original anchor; copying it does not relocate it.

Prefer NEW-side anchors beside the modified code when an exact diff
projection or a uniquely verified changed counterpart exists. The
identity bridge is useful evidence and a safe OLD-side fallback, not
a reason to hide explanations only beside deleted source.

Blob equality does not prove the target is visible. Verify each OLD
line or complete range occurs uniquely in the destination's actual
saved hunks, including their context. Tuicr can persist an off-hunk
comment that the current view cannot display. Preflight visibility
before adding any copy.

An original OLD-side comment does not use this bridge: its source is
the staged diff's base rather than its result. Other diff modes need
their own explicit blob correspondence and verified line/range map.
Do not reuse coordinates merely because they belong to the same file.

## Handle An Off-Hunk Anchor Explicitly

If an exact bridge lands outside the destination hunks, copying there
does not meet a request to see responses beside changed hunks.

1. Try an exact surviving-line projection into NEW-side coordinates.
   Use the actual index-to-worktree diff and require an unambiguous
   mapping inside a visible hunk. Matching blank or repeated lines by
   text, nearest-line offsets, or comment order is not identity proof.
2. If neither side exposes the exact anchor, report the affected
   original ID and coordinates during preflight. Options are
   a human-refreshed native view with wider context, a narrower batch,
   or an explicitly authorized semantic counterpart.
3. The normal `-r` policy, or an explicit revised-hunk mirror request,
   permits a
   semantic counterpart only when the response describes a specific,
   uniquely identifiable changed statement or explanation. Read the
   source, verify that exact counterpart in a destination hunk, and
   explain the selected NEW-side line/range. Record the snippet and
   transformation as a manual semantic projection, not an exact line
   map. If meaning or selection is ambiguous, ask for the target.

Never invent a CLI `hunk` target. Use the supported `line` or
`line_range` anchor. A semantic projection may change the range shape;
retain the source shape separately and verify the destination shape.
Do not change a source anchor, widen persisted hunks by hand, or mark
files reviewed to make comments visible.

## Add And Verify The Complete Mirror Batch

Prepare a manifest under the resolved ignored `review_replies` runtime
directory. Pin the source/destination identities and diff/blob hashes,
all source response and parent IDs, and one declared target mapping per
response. Record whether each mapping is an exact blob bridge, exact
surviving-line map, or manually verified semantic counterpart. Retain
the initial snapshots and any blocked preflight evidence.

Preflight the whole batch before the first write. Use the supported
payload fields and preserve each full body, author, type and null
commit identity. The mirror receipt associates the source session and
response ID with the destination session and returned copy ID; do not
rewrite original parent-ID markers to pretend they name local parents.
Do not copy human comments unless the human separately requests that.

Use the sequential `review add` and full verification procedure from
[tuicr-export.md](../../code-review/references/tuicr-export.md).
Before every addition, refresh both sessions and recheck scope, diff
identity, existing comments, and review state. Deduplicate by exact
body, author, type, commit identity and complete mapped anchor, never
title or counts. One matching copy can be reused; multiple matches
block the operation. A changed target after `git add` invalidates the
unstaged projection and requires a new native-view preflight.

After each addition, verify the returned ID and full persisted comment.
Range comments live in `line_comments[end_line]` with separate
`line_range: {start, end}`; single-line comments have a null range.
Verify the target side as well as the storage key, since OLD and NEW
line numbers may share a bucket. Preserve every existing comment and
reviewed/hunk marker in both sessions. Stop on drift or ambiguity and
report verified partial completion; do not restore over human state.

Finally re-list and reread both sessions, verify all intended copies,
and repeat reconciliation without writing to demonstrate idempotence.
Report counts, source-to-copy IDs, exact versus semantic projections,
and preservation evidence. Persisted visible anchors do not prove the
running TUI refreshed; do not equate `active: true` with live display.

## Review Iterations And Carrying Human Notes

Use the unstaged adjustment view for the human's next review pass.
Persist and read its selected follow-up comments directly; do not
require the human to retype them into a staged session. Before another
source edit, capture a fresh iteration baseline under the adjustment
handoff contract. Record each note's native ID, complete anchor, body,
author and diff/blob identity. The new baseline, not the first review's
old line numbers, defines what that iteration comments on.

When the human stages reviewed content and requests carrying those
notes forward, the common exact correspondence is:

**unstaged NEW text = captured worktree text = staged NEW text**

Prove that the note's captured NEW-side blob equals the current staged
NEW-side blob, and verify its line/range is visible in the native staged
hunks. Then its NEW coordinates can remain unchanged. Partial staging,
another source edit, and OLD-side notes require another verified map;
staged OLD means HEAD, not the earlier index. A note about removed code
may have no surviving inline counterpart. Report that case and request
a concrete counterpart or file-level carry; never guess the same line.

Select human notes through their explicit export/IDs or confirmed
authorship under the local-review contract. `-r` alone does not select
all human notes for transfer. A request to carry human notes authorizes
new copies, not their deletion; an explicit move request additionally
selects originals for eventual retirement through supported operations.

Preserve bodies, attribution, types and structural ranges. The add CLI
creates a new ID, so record source-to-copy aliases and the iteration
scope in the receipt. This is a verified carry-forward copy, not an
identity-preserving native move. Replies may still reference their
original parent ID in prose. Before responding again, reconcile those
verified aliases against the actual records to avoid duplicating an
already carried response; do not infer a parent relationship from
quotes or colocated comments. Human notes are never AI cleanup debris.

True moves and reply threading need native Tuicr support.
The inspected local CLI can carry notes through `review add`, but cannot
re-anchor or delete the original by ID. Disclose that copies remain in
both views until a supported retirement operation is available.

This limitation describes the inspected local binary, not every newer
release. Upstream deletion support below enables copy-then-retire once
the installed CLI exposes it; it still does not preserve IDs or add
native parent/reply threading.

## Staging Handoff And Mirror Retirement

Always render the adjustment-only diff and exact human staging command
under [review-adjustment-handoff.md](review-adjustment-handoff.md).
Alongside it, identify the mirror receipt and explain the post-stage
reconciliation step. Do not run `git add` or watch for staging in the
background. A human running the staging command is a source/index
transition, not blanket authority to delete session comments.

When the human subsequently requests reconciliation, verify the actual
staged blobs against the captured post-fix worktree blobs. Whole-file
equality permits the simple NEW-to-NEW map. Partial staging instead
needs a unique diff projection and proof that each carried edit actually
entered the index; retain copies for hunks which have not been staged.
No matching blob/unique hunk proof means no promotion or removal.

Before retiring an unstaged copy, preserve its explanation beside the
verified post-stage code in the appropriate native staged view, unless
the human explicitly chose retirement without promotion. For a NEW-side
unstaged mirror, unchanged worktree-to-index blob identity permits the
same NEW coordinates in the final staged diff. An OLD-side mirror needs
another proved line projection or changed-code counterpart; never reuse
its OLD coordinates blindly as staged NEW coordinates. Reuse one exact
existing staged response or add and verify an independent copy. Keep
the original human comments and source replies untouched.

Routine cleanup must address only returned AI mirror-copy IDs in the
receipt. Verify their full bodies, authors, source lineage, lifecycle,
anchors and unchanged reviewed/hunk markers immediately before removal.
Preserve any human follow-up or other comment, even at the same line;
never delete an entire bucket, file record or session to clear mirrors.
Local comments have no native parent/reply relationship, so colocated
comments are not proof that a whole group is expendable.

Human originals selected by an explicit move request have a separate
retirement set. Verify each selected ID and its preserved destination
copy with the same safeguards; never include them in routine AI mirror
cleanup or treat merely staging a file as approval to delete notes.

Inspect the installed `review --help` for a supported delete-by-ID
operation and recheck that operation's authorization/lock semantics.
The CLI verified on 2026-10-12 exposes only list/add/comments; automated
retirement is therefore unsupported. Do not invent a cleanup command,
edit session JSON, or promise that `git add` removes mirrors. Leave
those copies intact, report their exact pending IDs and the missing
capability, and provide verified native-UI removal instructions only
if that installed UI supports the operation.

Upstream `main` at `d02955aac01e0e074dccbf9916a90df57651e4ef`, checked
on 2026-10-13, supports this per-comment operation:
`review delete --session SESSION --comment-id ID --repo CHECKOUT`.
It refuses locked non-local-draft comments. Its
#773 change keeps an emptied session when a live TUI owns it and redraws
external deletions, including when other comments remain at that line.
Once the installed command advertises this operation, use it for the
verified retirement IDs only; all promotion and state gates still apply.
Never substitute `review clearc` or `review clear` for scoped cleanup.

The delete operation is ID-scoped, not a compare-and-swap on the checked
body/anchor. Avoid concurrent human edits to the selected copies during
retirement; if that cannot be established, report cleanup pending rather
than claim atomic snapshot protection. Re-read after each removal,
verify that exactly the selected ID disappeared, and preserve all other
comments and reviewed/hunk values. Do not update or build Tuicr merely
because a newer forge version exists; that requires separate authority.

Explain the threading limitation in the handoff: parent-ID prose and
mirror receipts provide auditable lineage, not local Tuicr threads.
Adding a human follow-up at the same anchor does not make it a native
reply-to-reply and must not cause cleanup to erase it.

## Validated Example

The 2026-10-12 Tractor logging review had 17 human comments and 17
responses in its staged session. Sixteen responses projected exactly
to visible unstaged OLD-side anchors. The fixture decorator's source
NEW line 278 fell outside the unstaged hunk on both equivalent sides.
The revised fixture explanation of `request.param=False/True` was
uniquely visible at NEW 294-296, so that response used a disclosed
semantic range counterpart and was verified under storage key 296.

The original session remained at 34 comments; the destination had 17
response copies. A second reconciliation added zero comments, and
source, index, original comments and file/hunk markers stayed unchanged.
These coordinates are historical evidence, not portable target values.
