# Review Adjustment Handoff

Use this handoff for every remote or local review that changes repository
content, whether or not local responses were authorized with `-r` or
`--respond`. It keeps review-driven adjustments visibly separate from the
pre-review work and leaves staging, commit planning, and committing under human
control.

## Capture The Pre-Edit Baseline

Before the first source edit in each receiving worktree:

1. Determine the complete path set that the accepted fixes may edit, create,
   delete, rename, or split. Include planned refactor destinations.
2. Record `HEAD`, the real index tree and stage entries, and which selected
   paths are staged, unstaged, untracked, absent, or mixed with unrelated work.
3. Build a private temporary index from `HEAD`. In that private index only, add
   the existing or tracked selected paths with `git add -A`, then write and
   retain its tree OID as `<pre-review-tree>`. Record selected paths that are
   absent separately. Remove the temporary index after the tree is written.
4. Verify that the real index tree and stage entries are unchanged.

Use `GIT_INDEX_FILE` or equivalent environment isolation for every private
index command. Store the temporary index beneath the worktree-specific Git
directory returned by `git rev-parse --git-path`; never use a shared fixed path.
The tree may write blobs for selected untracked files, so do not include
ignored, secret, or unrelated paths. Do not create a stash ref, commit, or
worktree for this snapshot.

The selected path set must be complete before editing. If a later fix needs a
pre-existing path that was not captured, stop before touching that path and
report that an isolated review-adjustment diff cannot yet be guaranteed. Never
silently present a combined pre-existing-and-review diff as review-only.

## Render Review Commands

After fixes and verification, render shell-correct commands with every path
quoted and an explicit `--` pathspec separator. For xonsh, keep each command on
one physical line.

### Default: review without changing the real index

Leave review adjustments unstaged and preserve the starting index.
After verification, build a fresh private index from `<pre-review-tree>`.
Use the same worktree-specific Git storage and `GIT_INDEX_FILE` isolation
as the pre-edit snapshot. In that private index only, add the final selected
paths with `git add -A` and retain its tree as `<post-review-tree>`.
Include deletions, both sides of renames and review-created files. Paths
absent from both that private index and the worktree remain recorded as
absent; do not pass nonexistent, untracked pathspecs to `git add`.

Verify that the real index tree and stage entries are unchanged, then
remove the private index. Do not use real-index intent-to-add to expose new
files in the default review flow: even that changes the starting index.

Render the review-only diff and its summary:

```text
git diff --find-renames <pre-review-tree> <post-review-tree> -- "<review-path>" ...
git diff --stat <pre-review-tree> <post-review-tree> -- "<review-path>" ...
```

These compare captured worktree states, not merely `HEAD` or the current
index. They include new files without mixing in pre-existing reviewed
changes or unrelated paths. Identify the reviewed snapshot; later source
edits invalidate it and require recapturing the affected final scope.

Default next step: review the diff, then invoke `/commit-plan`.
Planning accepts staged, unstaged and untracked changes; it owns commit
boundaries, checks, messages and eventual staging commands. Do not
recommend staging the whole review before planning: a staged combined
tree can conflict with the first of several boundaries. Do not unstage
existing human changes to make planning easier.

### Optional: explicitly chosen manual staging

Only when the human explicitly chooses manual staging, for example for
a single-commit `/commit-msg` flow, render the commands below. New files
can be exposed in a live worktree diff using intent-to-add; explain that
this changes the real index even though it does not stage their content.

```text
git add --intent-to-add -- "<new-path>" ...
git diff --find-renames <pre-review-tree> -- "<review-path>" ...
```

When every pre-existing change in the selected paths belongs to the reviewed
work, emit:

```text
git add -A -- "<review-path>" ...
```

This stages final reviewed path content, including deletions, and merges local
staged baselines with their unstaged fixes. If a selected path also contains
pre-existing work outside the review scope, emit the interactive form instead:

```text
git add -p -- "<mixed-path>" ...
```

Explain that the user must select only intended hunks. Never claim path-level
`git add -A` stages only review adjustments when a file contains mixed-owned
content. Do not stage anything while generating this handoff.

Local `-r` replies do not authorize staging. Reply-mirror cleanup follows
actual staging, not the completion of review remediation. Preserve this
distinction in both the default and explicitly chosen staging routes.

If no repository content changed, still report the baseline comparison result
but do not fabricate an empty `git add` command. If an explicitly authorized
cross-repository flow already committed the fixes, report that commit instead
of presenting stale diff or staging commands.

## Refresh Commit Plans

Repository content and commit-message context are inputs to `/commit-plan`.
When review fixes change either after a plan was generated, treat every
affected uncommitted boundary and its transitive dependants as stale. This
includes:

- added, deleted, renamed, split, or combined files;
- logic moved across planned boundaries or dependency order;
- any content change inside a pending boundary; and
- changed review, regression, or Prompt-IO message context.

Never reuse or render a prior archived message or execution command as
valid after such a change. This includes cached plan-executor invocations
and direct `git commit --edit` commands. After the user reviews the diff,
present `/commit-plan` as the next invocation without requiring staging.
That skill owns boundary re-evaluation, checks, message generation, and the
eventual shell-correct `git commit --edit --file ...` command.

If `/commit-plan` is unavailable in the active harness, stop after the diff
handoff and report the missing optional dependency. Do not substitute a
stale message, direct commit command, or ad hoc partial commit plan.

When neither repository content nor message context changed, report that the
prior plan remains only a refresh candidate; `/commit-plan` must still validate
its own fingerprints before reuse. `/code-review-changes` never edits a commit
plan receipt or generates a replacement commit message itself.
