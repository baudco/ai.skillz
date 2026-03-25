---
name: code-review-changes
description: >
  Address PR review comments: triage suggestions,
  apply valid code fixes in a worktree, and post
  inline reply comments via `gh`. Use when the user
  provides a GH review URL or asks to address PR
  review feedback.
argument-hint: "<PR-review-URL-or-PR#>"
disable-model-invocation: true
allowed-tools:
  - Bash(gh *)
  - Bash(git *)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(ls *)
  - Read
  - Grep
  - Glob
  - Write
  - Edit
---

When addressing PR review comments, always follow
this process:

## 0. Parse input and fetch review data

- Accept either a full GH review URL like
  `https://github.com/<owner>/<repo>/pull/<N>#pullrequestreview-<ID>`
  or a bare `<PR#>` (fetches ALL reviews on that
  PR).
- Extract `owner`, `repo`, `pr_number`, and
  optionally `review_id` from the URL.
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

- Create a worktree on the PR's head branch:
  ```
  git worktree add \
    .claude/worktrees/<slug> <branch>
  ```
  where `<slug>` is derived from the PR number
  (e.g. `pr<N>-review`).
- `cd` into the worktree for all subsequent file
  operations.
- Confirm the HEAD matches the PR's latest commit.

## 4. Apply code fixes

For each comment triaged as `fix`:

- Read the file at the relevant lines.
- Apply the minimal change that addresses the
  suggestion.
- Follow all project code-style rules (see
  `py-codestyle` skill if applicable).

## 5. Verify: run tests (mandatory)

**Before staging or committing**, run `/run-tests`
targeting the modules touched by your fixes (see
the change-type -> test mapping in that skill).

- If the worktree doesn't have its own venv, set
  one up first. For `uv`-managed projects:
  ```
  UV_PROJECT_ENVIRONMENT=py<MINOR> uv sync
  ```
  where `<MINOR>` matches the active cpython
  minor version (e.g. `py313` for 3.13, `py314`
  for 3.14). Detect via `python --version`.
- Use the worktree's Python binary to run pytest
  (e.g. `py<MINOR>/bin/python -m pytest ...`).

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
     guilty: <short-hash of your review commit>
     test: <test_name(s) that failed>
     cause: <1-line description of what broke>
     ```
     Example:
     ```
     guilty: 85457cb8
     test: test_stale_entry_is_deleted
     cause: `registry_addrs` change routes
       `addr` through msgpack -> list, not tuple
     ```
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

## 7. Post inline reply comments

For EVERY review comment (not just `fix` items),
post an inline reply via `gh api`:

```
gh api \
  repos/<owner>/<repo>/pulls/<N>/comments/<comment_id>/replies \
  -f body="<reply>"
```

### Reply format

Every reply MUST start with an attribution header:

```
> 🤖 *response authored by `claude-code`*
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
placeholder footer:

```
> 📎 commit pending
```

After the user commits and provides the hash
(or you detect it via `git log -1 --format=%h`),
PATCH each comment to replace the placeholder
with the real linked hash:

```
gh api \
  repos/<owner>/<repo>/pulls/comments/<id> \
  -X PATCH -f body="<updated-body>"
```

Track posted comment IDs so you can update them.

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
