# Local Tuicr Reviews

Use this workflow only for a persisted local Tuicr session. It substitutes
local session discovery for forge fetching and colocated comments for remote
thread replies; triage, fixes, tests, and summary stay shared with the parent
skill.

## 1. Resolve The User's Tuicr

Use the same executable and `HOME`/XDG environment as the user's TUI. Do not
install Tuicr, run a repository build, substitute another binary, or hardcode
a machine-local executable or storage path.

1. Resolve the command in the harness shell and show the executable and
   relevant `HOME`, `XDG_CONFIG_HOME`, and `XDG_DATA_HOME` values before using
   it. Preserve any environment assignments from the user's command.
2. If the user's command is a shell alias, function, or wrapper unavailable to
   the harness, ask for its concrete command expansion. Do not approximate it
   with the first `tuicr` on `PATH`.
3. As an optional fallback, when a matching live TUI process exists and the
   platform permits it, offer to inspect that process's executable and
   environment after user approval. Do not expose unrelated environment
   values or secrets.

All commands below use that resolved command and environment, represented as
`<tuicr>`.

## 2. Select The Session

The worktree being reviewed is the existing worktree supplied by the user or
the current worktree containing the requested session. Do not invoke
`/open-wkt` and do not create, switch, or relocate a worktree.

Run:

```bash
<tuicr> review list --repo <absolute-worktree>
```

Consider only entries with `"kind": "local"`. A path selector matches the
canonical checkout, but still verify all of these:

- the exact canonical worktree from the selected entry's persisted
  `repo_path`;
- the branch or detached anchor;
- the requested staged/unstaged mode, encoded by the slug source and persisted
  `diff_source` (`worktree`, `staged`, `unstaged`, combined, commit-range, or
  pristine variants);
- the supplied slug/path, when the user supplied one.

The `path` emitted by `review list` is the supported persisted session file;
read it only for fields omitted by `review comments`. Never derive or guess a
storage path. Ask the user to select when more than one session remains
plausible after the exact worktree, anchor, and mode checks.

## 3. Snapshot Comments And Review State

Before editing source code:

1. Run `review comments --session <session> --repo <absolute-worktree>`.
2. Read the selected session JSON at the `path` returned by `review list`.
3. Once human authorship is safely established, snapshot every selected human
   comment's immutable original anchor:
   `id`, `path`, `start_line`, `end_line`, `side`, and full `content`. Also
   retain its persisted `author` as selection evidence. Null target fields are
   valid for review-level and file-level comments.
4. Snapshot every file's `reviewed` value and complete `reviewed_hunks` set.
   These are user-owned state and must remain byte-for-byte equivalent as
   values throughout the workflow.

Keep the original snapshot after edits move source lines. Never relocate a
response to the comment's apparent new line.

### Human Authorship Limitation

Current `tuicr review comments` output omits `author`. The persisted session
schema does store `Comment.author`; old records without the field deserialize
as `"user"`. The TUI stamps local comments with its effective configured
`username`, but the CLI can stamp the same value, so an author string alone is
not universally proof that a human wrote the comment.

Select comments only when the user explicitly identifies particular comment
IDs as human-authored or confirms that an exact persisted author value
identifies their comments in this session. The TUI username from the same
`HOME`/`XDG_CONFIG_HOME` config may be presented as evidence, not treated as
proof. If authorship remains ambiguous, stop and report the limitation. Never
infer human authorship from content, username conventions, comment order, the
absence of an agent marker, or an omitted `author` field.

Ignore comments already known to be non-human, including prior responses, but
retain them when checking idempotency.

## 4. Triage, Fix, And Verify

Use the parent skill's `fix`, `ack`, `style-preference`, and `wontfix` model.
Apply only `fix` changes to the existing reviewed worktree and run the parent
skill's mandatory test workflow there. Skip the forge-only CI status query;
local access does not imply network authorization. Do not write the
forge-specific `.claude/review_context.md`; its `pr`, remote reply ID, and
commit-placeholder contract does not represent a local Tuicr session.

Adding responses is a separate mutation of user-owned review data. Do it only
when the current prompt explicitly requests it, for example, "add your
responses in Tuicr." A request to apply fixes or address code comments alone
does not authorize `review add`. Without authorization, finish fixes and tests,
then report proposed responses without mutating the session.

Never change file/hunk reviewed markers, remove or edit existing comments, or
claim that an individual local comment is resolved. Tuicr currently stores
independent local comments without a parent or resolved field.

## 5. Add Authorized Responses

Use one independent comment per selected human comment at its original
snapshot location. Give every addition an explicit agent username identifying
the harness/model; never rely on Tuicr's config fallback.

Each response body is exactly:

```text
> response authored by `<harness/model>`
> local response to Tuicr comment `<comment-id>`

<concise disposition and explanation>
```

The second line is the parent-ID marker used for idempotency while Tuicr has no
native reply relationship.

Before each addition, refresh `review comments` and search all comment bodies
for the exact parent-ID marker. If it exists, verify its original anchor and
count it as the already-added response; never add a duplicate after a retry or
interruption. If multiple markers exist, stop and report the duplicate state.

For an inline comment, invoke the resolved command with the original anchor:

```bash
<tuicr> review add \
  --session <session> \
  --repo <absolute-worktree> \
  --target-file <original-path> \
  --line <original-start-line> \
  --side <original-side> \
  --username "<harness/model>" \
  "<response>"
```

Add `--end-line <original-end-line>` whenever the original snapshot has an end
line, including when it equals the start line. For a file-level comment, use
only `--target-file`; for a review-level comment, omit all target flags. Never
invent absent line or side values, and pass generated content with shell-safe
argument handling rather than interpolating review data into shell syntax.

Add responses sequentially. After each command, refresh comments and verify
exactly one parent-ID marker, the returned response ID, full body, explicit
author in persisted JSON, and target fields equal to the original snapshot.
Stop on the first failed or ambiguous verification.

## 6. Refresh And Summarize

Before the final summary, rerun `review list`, `review comments`, and the
persisted-data snapshot. Include human comments added during the review. If a
new comment's authorship is safely established, triage it and repeat the
authorized response sequence; otherwise report the authorship gap without
guessing.

Verify and report:

- one response marker per selected human comment, whether newly added or
  safely detected from an earlier attempt;
- every response target matches its original anchor;
- all file and hunk reviewed state matches the initial snapshot;
- the refreshed session contains every persisted addition;
- when `active` is true, the TUI's persisted-session polling remains enabled
  and can merge additions. Persistence plus an active session demonstrates
  merge eligibility, not that the user has viewed the comment.

If reviewed state drifted, stop and report the mismatch without reverting
user-owned state or attributing a concurrent user change to the agent.

Report responses as **added** or comments as **addressed**. Do not use
"resolved" for local comments or equate comment lifecycle state with
resolution.
