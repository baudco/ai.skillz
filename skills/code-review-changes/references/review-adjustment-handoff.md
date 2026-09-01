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

When review fixes created untracked paths, emit this first so Git includes
their content in the review diff without staging it:

```text
git add --intent-to-add -- "<new-path>" ...
```

Then always emit the review gate:

```text
git diff --find-renames <pre-review-tree> -- "<review-path>" ...
```

This compares the final worktree to the captured staged or unstaged local
state, not merely to `HEAD` or the current index. It therefore shows the net
review-driven adjustment while preserving the reviewed baseline.

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

Never reuse or render a prior archived message or `git commit --edit` command
as valid after such a change. After the user reviews and stages the intended
paths, present `/commit-plan` as the next invocation. That skill owns boundary
re-evaluation, checks, message generation, and the eventual shell-correct
`git commit --edit --file ...` command.

If `/commit-plan` is unavailable in the active harness, stop after the diff and
staging handoff and report the missing optional dependency. Do not substitute a
stale message, direct commit command, or ad hoc partial commit plan.

When neither repository content nor message context changed, report that the
prior plan remains only a refresh candidate; `/commit-plan` must still validate
its own fingerprints before reuse. `/code-review-changes` never edits a commit
plan receipt or generates a replacement commit message itself.
