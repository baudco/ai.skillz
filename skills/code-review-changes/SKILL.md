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

### If tests fail

Determine whether the failure is:

1. **Pre-existing** (fails on the PR's HEAD
   commit *before* your changes too) - note it
   and move on.
2. **Caused by your review fixes** - this is a
   regression YOU introduced. Own it explicitly:
   - Fix the regression in the worktree.
   - When reporting to the user, clearly state
     that the regression was caused by your
     review changes, not the original PR code.
   - In any subsequent GH reply comments or
     commit messages, acknowledge the regression
     was self-inflicted, e.g.:
     > This fix addresses a regression introduced
     > by the review changes, not by the original
     > PR.
   - Re-run the affected tests to confirm the
     fix.

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
