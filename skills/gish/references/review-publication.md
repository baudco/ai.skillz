# Top-Level Review Publication

This contract publishes one human-approved, non-approving PR review body from
a local Markdown file. It is used by `/code-review` after that skill completes
its review and human-verification gate.

It does not cover inline comments, replies to existing comments, issue
creation, approval, change requests, source edits, commits, or Git pushes.

## Required Invocation

```text
/gish review-post <backend> <pr-num> \
  --repo <owner/name> --body-file <path> --sha256 <digest> \
  --head <commit> --event comment --actor <login>
```

All arguments are required. `comment` is the only accepted event in v1.
Reject aliases or backend-native values that mean approve, request changes,
pending, or draft.

## Authorization

The current human message must explicitly request publication of:

- the complete body already shown to them;
- the named backend, repository, and PR number;
- the recorded SHA-256 digest;
- the reviewed head commit;
- a non-approving top-level review comment.
- the authenticated account login which will publish it.

An initial review request, standing permission, approval of an older digest,
approval of a partial excerpt, or authorization to export JSON is not enough.
If `/code-review` delegates immediately from a current message containing
that exact approval, do not ask a redundant second question.

## Input Validation

Before network access:

1. Resolve `--body-file` without following an untrusted final symlink.
2. Require a regular file physically inside the active worktree.
3. Read it as UTF-8 and reject invalid encoding or NUL bytes.
4. Snapshot the bytes into a mode-0600 temporary regular file, compute
   SHA-256 over that snapshot, and compare it to `--sha256`.
5. Refuse an empty body.
6. Publish only from the validated snapshot, then remove it. Preserve the
   source file after success or failure as the local publication record.

Do not alter whitespace, append attribution, convert Markdown, or substitute
the JSON review export. `/code-review` owns its disclosure before approval and
digesting; `gish` validates and publishes the candidate byte-for-byte. Do not
infer a disclosure requirement for arbitrary `review-post` callers without an
explicit content-kind or provenance contract.

## Target Validation

Resolve the repository from the selected backend and active worktree. Before
posting:

1. Fetch only the target PR metadata needed for publication.
2. Require the remote PR head commit to equal `--head` exactly.
3. Require the PR to remain open and reviewable.
4. Require the authenticated account and repository to match the target shown
   during human approval.
5. Stop on drift, ambiguity, missing credentials, or backend errors.

The content layer owns base and merge-base validation. `gish` independently
pins publication to the remote head to close the final transport race.

## GitHub Adapter

GitHub publication is supported through authenticated `gh`. Resolve the
repository name and verify PR metadata first, then create a review with:

```text
gh api repos/<owner>/<repo>/pulls/<pr-num>/reviews \
  --method POST \
  --raw-field event=COMMENT \
  --raw-field commit_id=<head> \
  --field body=@<body-file>
```

Use file upload semantics so the Markdown body is not reconstructed through
shell interpolation. Capture the resulting review ID and HTML URL. Report
both when available.

Do not use `gh pr review --approve`, `--request-changes`, or an inline review
API from this operation.

Use `scripts/review-post.py` for validation and transport. Do not manually
recreate its path, digest, target, or head checks.

## Other Backends

Gitea, GitLab, and sourcehut top-level review publication are unavailable in
v1. Preserve the approved body and report the missing adapter. Do not infer a
service API call from GitHub's implementation.

Adding a backend requires:

- an equivalent non-approving top-level event;
- exact body-file transport;
- remote head pinning;
- returned publication identity or URL;
- contract tests that prove approval and drift failures remain fail-closed.

## Result

On success report:

- backend, repository, and PR number;
- reviewed head and approved SHA-256 digest;
- review ID and URL;
- preserved local body path.

Publication grants no follow-up authorization. A corrected or additional
review body must pass the complete approval flow again.
