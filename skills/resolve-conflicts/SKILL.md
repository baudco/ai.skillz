---
name: resolve-conflicts
description: >
  Resolve git merge/rebase conflicts by analyzing all
  sides and reconciling changes. Use when git reports
  unmerged paths during rebase, merge, or cherry-pick.
argument-hint: "[optional-file-path]"
disable-model-invocation: true
allowed-tools:
  - Bash(git *)
  - Bash(python -c *)
  - Read
  - Edit
  - Grep
  - Glob
---

Resolve git conflicts by understanding *why* each side
changed, then producing a resolution that preserves
every intended change. Follow this process:

## 0. Detect conflict state

Run `git status` to confirm an in-progress rebase,
merge, or cherry-pick and identify all unmerged paths.

If an argument was given, scope to that file; otherwise
process ALL unmerged files.

Tell the user which operation is in progress and list
the conflicted files.

## 1. For EACH conflicted file

### a. Locate conflict markers

Find all `<<<<<<<` / `=======` / `>>>>>>>` regions
in the file using `grep -n`.

### b. Identify the three sides

The meaning of "ours" vs "theirs" depends on the
git operation:

- **rebase**: `HEAD` (aka `<<<`) = the branch being
  rebased *onto* (upstream/main); `>>>` = the commit
  being replayed (your work).
- **merge**: `HEAD` = your current branch; `>>>` =
  the branch being merged in.
- **cherry-pick**: `HEAD` = your current branch;
  `>>>` = the commit being picked.

State which side is which so the user can verify.

### c. Understand each side's intent

For each conflict region, determine what each side
was trying to accomplish:

1. **Read the HEAD version** of the hunk in full.
2. **Read the incoming version** of the hunk in full.
3. **Find the merge base version** to understand what
   the file looked like before either side changed it:
   ```
   git merge-base HEAD MERGE_HEAD  # merge
   git merge-base HEAD $(cat .git/rebase-merge/stopped-sha)  # rebase
   ```
   Then `git show <base>:<file>` to read the
   original. If unavailable, infer from context.
4. **Diff each side against the base** to isolate
   exactly what each side added, removed, or moved.

### d. Check for code movement

A common pattern: one side *moved* code to a new
file while the other side *modified* that same code
in place. When this happens:

1. Identify the destination file (check staged new
   files, renamed files, or import/alias lines in
   the conflict).
2. Read the destination file.
3. Diff the moved copy against the modified-in-place
   copy to find changes the destination is missing.
4. Apply those missing changes to the destination.
5. Resolve the conflict in the original file by
   keeping the import/alias (or deletion) — i.e.
   accept the "moved" side's version of the
   original file.

### e. Produce the resolution

- If both sides made non-overlapping changes,
  combine them.
- If one side is strictly a superset of the other,
  keep the superset.
- If changes genuinely conflict (same line, different
  intent), flag it to the user and propose options.

Use the `Edit` tool to replace the entire conflict
region (including markers) with the resolved code.

## 2. Validate

After resolving all conflicts in a file:

1. **Syntax check**: run
   `python -c "import ast; ast.parse(open('<file>').read())"` for `.py` files
   (or equivalent for other languages).
2. **No stale imports**: check whether the resolution
   left behind imports that are no longer needed
   (e.g. a type was moved out but its import
   remains).
3. **No leftover markers**: `grep -n '<<<<<<\|=======\|>>>>>>' <file>` must be empty.

## 3. Report

Summarize for the user:

- Which files were resolved and how.
- Any changes propagated to destination files
  (code-movement cases).
- Anything that needs manual review.
- Remind them to `git add <files>` and continue
  the rebase/merge/cherry-pick when ready.

## Important

- **Never** `git add` or `git rebase --continue`
  automatically — let the user do that.
- **Never** discard changes from either side without
  telling the user why.
- When in doubt about intent, show both versions
  and ask the user which to keep.
- Follow the project's `py-codestyle` conventions
  when touching code (67 char lines, single quotes,
  etc.).
