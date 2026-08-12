---
name: close-wkt
description: >
  Close (teardown) a git worktree opened via
  /open-wkt. Shows a summary of work done and
  optionally removes the worktree + branch.
compatibility: >
  Requires git CLI.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[<name>] [--discard-worktree] [--delete-unmerged-branch] [--keep-branch] [--takeover] [--recover-guard <token>]"
disable-model-invocation: true
allowed-tools:
  - Bash(git *)
  - Bash(rm *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Bash(date *)
  - Bash(cat *)
  - Read
  - Glob
  - Grep
---

Close a worktree previously opened via `/open-wkt`.

## Invocation

```
/close-wkt [<name>] [--discard-worktree] [--delete-unmerged-branch] \
  [--keep-branch] [--takeover] [--recover-guard <token>]
```

### Parameters

- **`name`** (optional): worktree name. If omitted,
  infer from cwd (must be inside a `wkts/`
  subtree).

- **`--discard-worktree`** (optional): explicitly discard uncommitted and
  untracked work while removing the worktree. Without this exact flag, stop on
  a dirty worktree; a general teardown request is not discard authorization.

- **`--delete-unmerged-branch`** (optional): after listing commits unique to
  the worktree branch, explicitly authorize deleting that branch even when it
  is not merged. This is independent of `--discard-worktree`.

- **`--takeover`** (optional): explicitly acquire ownership from the recorded
  session/agent before teardown. Show the prior owner and lock age first.

- **`--recover-guard <token>`** (optional): explicitly resume or release a
  guard left by an interrupted teardown after inspecting its owner token,
  recorded phase, worktree registration, and filesystem state. A matching
  owner token alone is not recovery authorization.

- **`--keep-branch`** (optional): don't delete the
  `wkt/<name>` branch after removing the worktree.
  Useful when you want to preserve commits for later integration.

## Protocol

**Interrupted-teardown recovery runs first.** When the current prompt includes
`--recover-guard <token>`, resolve the common Git directory from the main
repository and read the matching guard before requiring a registered worktree
or private worktree Git directory. Validate the guard's recorded name,
canonical path, branch, owner, and phase. If the worktree is already
unregistered, verify the recorded path is absent or inventory any surviving
files, preserve the branch unless the current prompt separately authorizes its
deletion, report the recovered state, and release the guard. Never require
deleted private-Git-dir metadata to recover a post-removal guard.

When invoked from a linked worktree, derive the main repository root from the
absolute common Git directory and verify it against `git worktree list
--porcelain`; do not use the linked worktree's `--show-toplevel` as the main
root. The resulting main root owns the canonical `wkts/` parent.

1. **Validate the managed target and locate metadata**: require `<name>` to
   satisfy the same snake_case rule as `/open-wkt`; reject separators, `..`,
   leading dots/dashes, and any canonical path outside
   `<repo-root>/wkts/<name>`. Resolve the repository root first, reject a
   symlinked or out-of-repository `wkts` parent, and use the absolute canonical
   path for every command. Verify `git worktree list --porcelain`
   maps that exact path to the branch recorded in metadata before destructive
   Git operations. Newly created worktrees require `wkt/<name>`; a migrated
   pre-existing branch is allowed only when metadata records
   `branch_exception: true` and its exact branch matches both registration and
   metadata. Read
   `<worktree-git-dir>/ai-skillz-wkt/meta.json` for lifecycle info (parent
   branch, notify preference, etc.). Resolve the private Git directory from
   the exact registered worktree path; do not use a literal `.git/` path.

2. **Acquire the teardown guard and verify ownership**: atomically create
   `<common-git-dir>/ai-skillz-wkt-locks/<name>.guard`, outside every worktree,
   and hold it through inventory, worktree removal, branch handling, and the
   final report. Write the owner token and current teardown phase inside the
   guard together with the canonical worktree path, branch, and the lifecycle
   fields needed after Git removes the private worktree directory. Update this
   recovery snapshot to `removing`, then `removed`, around worktree removal. If
   acquisition fails, inspect that record and stop unless the current
   prompt explicitly names `--recover-guard <token>`; age alone does not
   authorize resuming or removing it. While holding it, read
   `<worktree-git-dir>/ai-skillz-wkt/owner.json` and compare
   its exact token with the current provider/session/agent token. If they
   differ, release the newly acquired unchanged guard before stopping. A stale
   timestamp is not permission to proceed; require an explicit
   current-prompt `--takeover`, report the prior owner and age, re-read the
   owner, and if it changed, release the unchanged guard before stopping. Then
   record the new owner without releasing the teardown guard.

3. **Notify** (if `notify_on_teardown` is true):
   - Show uncommitted changes:
     `git -C <repo-root>/wkts/<name> diff --stat`
   - Show untracked files:
     `git -C <repo-root>/wkts/<name> status --short`
   - Resolve `<managed-branch>` from the exact registered branch and metadata.
   - Show commits made on this worktree branch:
     `git log <parent_branch>..<managed-branch> --oneline`
   - Show commits unique to the branch with
     `git log --oneline --decorate <parent>..<managed-branch>`.
   - If there are uncommitted or untracked changes and
      `--discard-worktree` is not present in the current request, stop and show
      the exact flag needed. Do not treat branch-deletion authorization as
      permission to discard files. Release the unchanged teardown guard before
      this safe refusal.

4. **Return to main repo**:
   `cd` to the repo root (NOT the worktree).

5. **Remove the worktree** while retaining ownership until teardown starts:
   ```sh
   git worktree remove <repo-root>/wkts/<name>
   # only with explicit --discard-worktree
   git worktree remove --force <repo-root>/wkts/<name>
   ```

6. **Delete the branch** (unless `--keep-branch`):
   ```sh
   git branch -d <managed-branch>
   # only after --delete-unmerged-branch and the unique-commit report
   git branch -D <managed-branch>
   ```

   Try `-d` first. If Git refuses because the branch is unmerged, preserve the
   branch and stop unless the current prompt includes
   `--delete-unmerged-branch`. `--discard-worktree` never implies `-D`.
   A normal `-d` refusal is a safe terminal outcome: preserve the branch and
   continue to step 7 so the teardown guard is released.

7. **Report and release**: print a terse summary of what was
   cleaned up (branch deleted? commits preserved?
   changes lost?), then remove the common-dir teardown guard. On a handled
   command failure, inspect and record the resulting phase. Release the guard
   when no destructive command remains active and the worktree is still
   safely owned; otherwise preserve it and report the exact token and phase
   needed for an explicit `--recover-guard` request. Never leave an
   unidentifiable guard or remove one merely because a branch deletion was
   refused.

## Edge cases

- **Unregistered worktree** (directory exists but Git does not track it): do
  not prune or remove it automatically. Verify the same ownership contract,
  inventory all files, and require explicit `--discard-worktree` before
  deleting any non-empty directory. `git worktree prune` may clean stale Git
  administrative records after that separately authorized filesystem removal;
  it is not evidence that the directory is disposable.

- **No metadata or ownership record**: inspect and report, then stop. Do not
  infer teardown ownership or destructive defaults.

- **Cwd IS the worktree**: must `cd` out before
  `git worktree remove` will work.
