---
name: code-review-changes
description: >
  Address PR review comments: triage suggestions,
  apply valid code fixes in a worktree, and post
  inline reply comments via `gh`. Use when the user
  provides a GH review URL or asks to address PR
  review feedback.
compatibility: >
  Requires authenticated gh CLI and git CLI.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "<PR-review-URL | PR# --repo owner/name>"
disable-model-invocation: true
allowed-tools:
  - Bash(gh *)
  - Bash(git *)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(ls *)
  - Bash(sha256sum *)
  - Read
  - Grep
  - Glob
  - Write
  - Edit
---

When addressing PR review comments, always follow
this process:

## 0. Parse input and fetch review data

Before any forge query, require explicit current-prompt network authorization.
Supplying a review URL or asking to address feedback authorizes neither network
access nor remote publication. If authorization is absent, use complete review
content supplied locally or ask one short network-access question and stop.

- Accept either a full GH review URL like
  `https://github.com/<owner>/<repo>/pull/<N>#pullrequestreview-<ID>`
  or `<PR#> --repo <owner/name>` (fetches all reviews on that PR). A bare PR
  number without an explicit repository is ambiguous; ask one short repository
  question before any network access and never infer it from cwd or remotes.
- Extract `owner`, `repo`, `pr_number`, and
  optionally `review_id` from the URL.
- Query `/gish inspect-pr gh <N> --repo <owner>/<repo>` under the same explicit
  network authorization. Record the head repository, head ref, and head OID;
  branch names alone are not authoritative, especially for fork PRs.
- Fetch review comments via `gh api`:
  ```
  gh api repos/<owner>/<repo>/pulls/<N>/comments \
    --paginate
  ```
  If a specific `review_id` was given, filter
  comments to those matching
  `.pull_request_review_id == <review_id>`.

## 1. Check the PR description for TODOs

- Fetch the PR body:
  ```
  gh pr view <N> --repo <owner>/<repo> \
    --json body,title
  ```
- Scan for TODO bullets, checkboxes, or
  outstanding items. Report any that are not yet
  addressed by existing commits on the branch.

## 2. Triage each review comment

For each comment, determine:

- **File + line**: from `.path` and `.line` /
  `.original_line`
- **Symlink check**: if the file is a symlink,
  resolve the target via `readlink -f`. Record:
  * `canonical_path`: the resolved absolute path
  * `canonical_repo`: the git repo root containing
    the target (`git -C <dir> rev-parse
    --show-toplevel`)
  * `is_cross_repo`: whether `canonical_repo`
    differs from the PR repo
  When `is_cross_repo` is true, fixes must be
  applied in the canonical repo, not the PR
  worktree. Note this in the triage table with an
  extra column or annotation (e.g. "fix in
  ai.skillz").
- **Suggestion**: extract the core ask
- **Validity**: read the current code on the PR
  branch to verify whether the suggestion is
  correct, already addressed, or inapplicable
- **Action**: one of:
  * `fix` - valid suggestion, apply code change
  * `ack` - valid observation, already addressed
    in a later commit
  * `style-preference` - disagree / project style
    choice, reply explaining why
  * `wontfix` - invalid or N/A, reply explaining

Present a summary table to the user:

```
| # | File | Comment | Valid? | Action |
|---|------|---------|--------|--------|
```

## 3. Set up a worktree for changes

- Require the deployed `/open-wkt` companion and invoke it with the verified PR
  head OID, not a same-named local branch:
  ```
  /open-wkt <slug> --start-point <head-oid>
   ```
   where `<slug>` is derived from the PR number
   using valid snake_case (e.g. `pr<N>_review`).
- If `/open-wkt` is unavailable, stop without creating an unmanaged worktree.
- Switch into its `.claude/wkts/<slug>` worktree for all subsequent file
  operations.
- Confirm the new worktree HEAD equals the forge-reported head OID. If the
  object is missing, stop; fetch the exact head repository/ref only when the
  current prompt authorized that network operation, then verify its OID.

## 4. Apply code fixes

For each comment triaged as `fix`:

- Read the file at the relevant lines.
- Apply the minimal change that addresses the
  suggestion.
- Follow all project code-style rules (see
  `py-codestyle` skill if applicable).

### Cross-repo symlink fixes

When a fix targets a symlinked file with
`is_cross_repo == true`:

- Report the exact canonical repository and target path, then require explicit
  current-prompt authorization to modify that separate repository. PR review
  remediation authorization for the submitted repository does not imply it.
- In the canonical repository, resolve its current head OID and invoke
  `/open-wkt crossrepo_pr<N>_review --start-point <canonical-head-oid>`. Stop if
  the companion is unavailable or the name is already owned by another
  session.
- Map `canonical_path` to the equivalent path inside that managed canonical
  worktree and edit only that copy, not the original checkout or the symlink.
  Track this worktree as the receiving repository for tests, context, staging,
  and commit steps.
- Track each distinct `canonical_worktree_root` that receives fixes. Those
  managed worktrees need their own test, context, stage, and commit cycle.
- The original PR-worktree symlink may not point at the canonical worktree.
  Verify the fix against the managed canonical copy and compare the intended
  PR path semantically; do not mutate the symlink merely to make it visible.

## 5. Verify: run tests (mandatory)

**Before staging or committing**, group changed files
by the repository that receives them. From each
repository/worktree root, run `/run-tests` targeting
the modules changed there. This ensures cross-repo
fixes use the managed canonical worktree's environment and
`test-harness-reference.md`, not the PR repository's.

The active provider session must have the canonical
`/run-tests` skill available. Each changed repository
must provide its own harness reference or sufficient
project metadata. Deploying into another repository
does not hot-load that skill into the current session;
stop and request a restart when it is unavailable.

- Delegate environment selection and validation to
  `/run-tests` and the repository's local harness
  reference. If the required environment is missing,
  report the missing prerequisite and ask before
  creating it or running `uv sync`.
- Never modify a lock file as an implicit test setup
  step. When the user approves an existing-lockfile
  sync, prefer the repository-documented locked mode.

### Establish CI baseline

Before attributing any failure to your changes,
check the PR's HEAD commit CI status:

```
gh api \
  repos/<owner>/<repo>/commits/<head-sha>/check-runs \
  --jq '.check_runs[] |
    "\(.name): \(.conclusion)"'
```

If all checks passed on the prior commit, any
new failure is likely caused by your changes.

### If tests fail

Determine whether the failure is:

1. **Pre-existing** (CI was already red on this
   test, or it fails on the PR's HEAD commit
   *before* your changes too) - note it and
   move on.
2. **Caused by your review fixes** - this is a
   regression YOU introduced. Own it explicitly:
   - Fix the regression in the worktree.
   - When reporting to the user, clearly state
     that the regression was caused by your
     review changes, not the original PR code.
   - In any subsequent GH reply comments or
     commit messages, acknowledge the regression
     was self-inflicted.
   - Re-run the affected tests to confirm the
     fix.
   - **Write a regression context file** at
     `.claude/review_regression.md` so that
     `/commit-msg` can incorporate it. Format:
     ```
      guilty: pending
     test: <test_name(s) that failed>
     cause: <1-line description of what broke>
     ```
     Example:
     ```
      guilty: pending
     test: test_stale_entry_is_deleted
     cause: `registry_addrs` change routes
       `addr` through msgpack -> list, not tuple
      ```
      `pending` is intentional because verification
      occurs before the review-fix commit exists.
      Write this file under the repository where the
      failing review fix lands, using the same
      placement rule as `review_context.md`. For
      multi-repository fixes, write one scoped artifact
      per receiving repository.
     The `/commit-msg` skill reads this file and
     folds its content into the commit message
     body, then deletes it after use.

### Confirming green

Re-run the full targeted test subset to ensure
all pass. Only proceed to step 6 once green.

## 6. Present changes for user review

**NEVER auto-commit.** After fixes pass tests:

- Tell the user what files changed and why.
- Show the diff summary.
- Suggest they review the worktree state, stage
  files manually, and use `/commit-msg` (inline
  or in a separate session) to generate commit
  content.
- **Do NOT push** - the user must push manually
  (no SSH key access assumed).

### Write review context file

Write `.claude/review_context.md` so `/commit-msg`
can add a `Review:` trailer. **Placement rule**:
write it to the repo where the `fix` changes
actually land — i.e. `<canonical_worktree_root>/.claude/`
when cross-repo symlink fixes were applied, NOT
the PR repo. This ensures `/commit-msg` finds
the context when run from the correct repo.

If fixes span multiple repos (rare), write a copy
to each repo that received changes and identify that
repository in `commit_repo`.

Initial contents (before GH replies are posted):

```
pr: <N>
repo: <owner>/<repo>
commit_repo: <owner>/<repository-receiving-the-fix>
review_url: <full-review-URL-or-PR-URL>
reviewer: <reviewer-login>
actions: fix=<n> ack=<n> wontfix=<n>
```

The `reply_ids` and `reply_files` fields are appended in step 7 after
comments with pending-commit placeholders are posted. If the review was fetched
by bare PR number (no specific `review_id`),
use the PR URL as `review_url`.

### Cross-repo commit flow

When `is_cross_repo` fixes exist, drive the
commit from this session rather than deferring
to a separate session in the other repo:

1. Show the exact changed paths and current index, then require an explicit
   current-prompt request to stage those paths. Applying fixes or approving a
   commit message is not staging authorization.
2. Only after that request, stage the changed files in the managed canonical
   worktree:
   ```
   git -C <canonical_worktree_root> add <changed-files>
   ```
3. Show the staged diff to the user for review.
4. Generate the commit message inline (same
   rules as `/commit-msg` — pick up
   `review_context.md` from that repo).
5. Ask the user to confirm, then commit:
   ```
   git -C <canonical_worktree_root> commit \
     --edit --file <msg-file>
   ```
6. Read back the hash:
   ```
   git -C <canonical_worktree_root> log -1 --format=%h
   ```
7. Use the hash in the complete reply candidates in step 7. Present those
   final bodies for exact publication approval; no placeholder is needed when
   the commit happens before replies are posted.

When the fix commit is in a different repo than
the PR, use that repo's remote URL for the
commit-ref footer link (e.g.
`https://github.com/baudco/ai.skillz/commit/`
instead of the PR repo's URL).

## 7. Post inline reply comments

Do not post remote replies until a current human message explicitly approves
the complete reply body, backend, repository, PR, parent comment, and publish
action. Acceptance of fixes, commit authorization, or an earlier draft is not
publication authorization. If the user
has not committed yet, also ask whether to wait for the
real hash or post approved placeholders. A review
handoff is not authorization to publish comments.

For every review comment, write the complete reply first under
`<fix-repo-root>/.claude/review_replies/<parent-id>_candidate.md`, compute its
SHA-256 digest, and show the rendered body plus exact target arguments. After
the separate approval above, first write
`<parent-id>_publication.json` beside the candidate with the exact target,
digest, candidate path, and `remote_id: null`. Then publish through
`/gish comment-reply` with the
repository, PR, parent comment, verified head OID, path, line, side, candidate
file, and digest. On success, atomically replace `remote_id: null` with the
returned ID before processing another reply. Preserve the record on failure so
an interrupted run can reconcile the exact attempted publication. Never
interpolate reply Markdown into a shell command.

### Reply format

Every reply MUST start with an attribution header
derived from the active coding harness:

```
> response authored by `<harness>`
```

Followed by a blank line, then the reply body.

### Reply content by action type

- **fix**: briefly describe what was changed.
- **ack**: note that this was already addressed
  in a prior commit.
- **style-preference**: explain the project's
  convention and why the current code is
  intentional.
- **wontfix**: explain why the suggestion doesn't
  apply or is incorrect.

Keep replies concise and technical. Don't
duplicate info that's already obvious from the
commit footer (see below).

### Commit-ref footer

Every reply MUST end with a blockquote footer
linking the relevant commit(s). Use a linked
short-hash pointing at the hosting service's
commit URL. The verb conveys the disposition:

- **fix**:
  ```
  > 📎 fixed in [`<hash>`](<commit-url>)
  ```
- **ack** (already done in an earlier commit):
  ```
  > 📎 already addressed in [`<hash>`](<commit-url>)
  ```
- **wontfix** / **style-preference**: only include
  a commit footer if there's a specific commit
  that demonstrates *why* the suggestion doesn't
  apply (e.g. the commit that introduced the
  intentional pattern). If the reason is purely
  conceptual, skip the footer - don't fabricate a
  ref just for the sake of it.
  ```
  > 📎 see [`<hash>`](<commit-url>) for context
  ```

Determine the commit-URL base from `git remote`:
- `github`/`origin` ->
  `https://github.com/<owner>/<repo>/commit/`
- `gitea` -> parse the remote URL
- `srht` ->
  `https://git.sr.ht/~<owner>/<repo>/commit/`

When multiple commits address a single comment,
chain them:
```
> 📎 fixed in [`abc1234`](<url>) [`def5678`](<url>)
```

### Posting before commit exists

Since the user commits manually (step 6), the
final commit hash may not exist yet when posting
replies. Post comments immediately with a
placeholder footer only when that exact candidate and placeholder publication
were separately approved:

```
> 📎 commit pending
```

After the user commits and provides the hash (or a new HEAD is detected),
prepare the complete local replacement body and its SHA-256 digest. Detection
of the commit does not authorize a remote edit. Require a separate current
human message approving that exact body, digest, backend, repository, comment
ID, and edit action, then publish through `/gish comment-edit`. Preserve the
candidate on missing approval or failure.

Track posted comment IDs so separately approved edits can target them.
For every posted placeholder reply, also preserve the exact submitted body in
`<fix-repo-root>/.claude/review_replies/<id>_pending.md`, where
`<fix-repo-root>` is the same repository receiving `review_context.md` under
the placement rule in step 6. Record paths relative to that root in
`reply_files`. This local source lets
`/commit-msg` prepare a complete replacement without an unauthorized network
read.

### Update review context with reply IDs

After posting all reply comments, append the `reply_ids` and `reply_files`
fields to `.claude/review_context.md`
(written in step 6). List the IDs of replies whose
footer still reads `> 📎 commit pending` so that
`/commit-msg` (or a follow-up session) can tell
the user which comments need PATCHing with the
real commit hash:

```
reply_ids: <id1>,<id2>,...
reply_files: <id1>=.claude/review_replies/<id1>_pending.md,<id2>=.claude/review_replies/<id2>_pending.md
```

If no replies were posted (all comments were
`ack`/`style-preference` with no placeholder
footer), omit `reply_ids` from the file.

## 8. Summary

After all comments are addressed, present:

- Worktree path + list of modified files
- Reminder to review, stage, commit, and push
- Count of comments addressed by type
  (fix/ack/style/wontfix)
- Any regressions introduced (and fixed) by
  review changes - be explicit about self-caused
  breakage vs pre-existing issues
- Any unresolved PR-description TODOs
