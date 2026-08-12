---
name: open-wkt
description: >
  Open (create + enter) a git worktree for isolated,
  ephemeral work. Manages lifecycle from creation
  through teardown with optional fixturization.
compatibility: >
  Requires git CLI. Optional: uv for venv
  fixturization.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "<name> [--start-point <oid>] [--fixturize] [--notify-on-teardown] [--takeover] [--recover-guard <token>] [--migrate-legacy]"
disable-model-invocation: false
allowed-tools:
  - Bash(git *)
  - Bash(ln *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Bash(chmod *)
  - Bash(rm *)
  - Bash(date *)
  - Bash(cat *)
  - Read
  - Write
  - Glob
  - Grep
---

Open (or re-enter) a git worktree for isolated work.

## Naming + directory schema

Worktrees live under `<repo-root>/wkts/<name>/` where
`<name>` is a **snake_case semantic label** describing
the *work being done*, NOT necessarily the git branch
name.

Examples:
- `fix_sigint_flaky_timeout`
- `pr366_review_fixes`
- `refactor_pr_msg_line_len`
- `proto_wkt_skill`

The git branch created for the worktree follows the
pattern `wkt/<name>`
(e.g. `wkt/fix_sigint_flaky_timeout`).

The root-level `wkts/` directory is provider-neutral. Do not create
harness-named aliases such as `claude_wkts` or store worktrees beneath
`.claude/` or `.opencode/`.

## Invocation

```
/open-wkt <name> [--start-point <oid>] [--fixturize] [--notify-on-teardown]
```

### Parameters

- **`name`** (required): snake_case label for the
  worktree. Used as directory name and branch suffix.

- **`--start-point <oid>`** (optional): create the worktree branch from this
  exact local commit instead of current `HEAD`. Require a full OID that resolves
  to a commit; this option does not authorize fetching a missing object.

- **`--fixturize`** (optional, default: false): when
  set, run `UV_PROJECT_ENVIRONMENT=.venv uv sync`
  inside the worktree to create a local venv so
  tests/tooling work in isolation. The venv dir name
  (`.venv`) avoids collision with the main repo's
  venv (which may use a custom name like `py313/`).

- **`--notify-on-teardown`** (optional, default:
  true): when the worktree is closed via `/close-wkt`,
  print a summary of what changed (diffstat,
  uncommitted files) before prompting for removal.
  When false, teardown is silent (useful for fully
   automated subagent work).

- **`--migrate-legacy`** (optional): explicitly move one registered
  `<repo-root>/.claude/wkts/<name>` worktree to `<repo-root>/wkts/<name>`.
  This is a one-way migration, not a compatibility mode.

## Creation protocol

0. **Resolve the repository root and destination**: use `git rev-parse
   --show-toplevel` from the main checkout, then use the absolute
   `<repo-root>/wkts/<name>` path for every check and command. Reject a `wkts`
   parent which is a symlink, is not a directory, or canonicalizes outside the
   repository root. Create the real root-level parent only after validation.

1. **Validate name**: ensure `<name>` is snake_case,
   no spaces, no leading dots/dashes.

2. **Check for existing**: if `<repo-root>/wkts/<name>/`
   already exists, re-enter it instead of creating
   a new one. Print a notice. Before creating, also inspect `git worktree list
   --porcelain` for the exact legacy path
   `<repo-root>/.claude/wkts/<name>`. If registered, stop and require the exact
   `/open-wkt <name> --migrate-legacy` request regardless of its branch name.

3. **Acquire the creation guard**: resolve the common Git directory, create
   its shared lock parent with `mkdir -p <common-git-dir>/ai-skillz-wkt-locks`,
   then atomically create `<name>.guard`. Write the owner token and `creating`
   phase inside it. Do this before creating a branch or worktree. If the guard
   exists, stop and report its owner/phase. Recovery requires an explicit
   current-prompt `--recover-guard <token>` after inspecting whether the branch,
   worktree, and owner record were partially created; age alone is insufficient.

4. **Create the worktree** while holding the guard:
   ```sh
    git worktree add \
      <repo-root>/wkts/<name> \
      -b wkt/<name> [<start-point-oid>]
    ```
   Without `--start-point`, this branches from current HEAD.

5. **Write lifecycle metadata outside the worktree**: resolve the linked
   worktree's private Git directory with `git -C <repo-root>/wkts/<name> rev-parse
   --git-dir`, create its `ai-skillz-wkt/` directory, and write `meta.json`
   there:
   ```json
   {
     "name": "<name>",
     "branch": "wkt/<name>",
     "parent_branch": "<current-branch>",
     "created": "<ISO-8601 timestamp>",
     "fixturized": false,
      "notify_on_teardown": true,
      "status": "active",
      "branch_exception": false
   }
   ```
   Git administrative storage keeps this metadata out of status and commits.

6. **Finalize worktree ownership atomically**:
   Derive a stable owner token from the current provider, session, and agent
   identity. Do not use a generic value such as `active`. Serialize every
   initial creation already holds the common-dir guard from step 3. Require
   `<worktree-git-dir>/ai-skillz-wkt/owner.json` to be absent, then write the
   exact owner token,
   provider, session, agent, and acquisition timestamp. Release the guard only
   after the owner record is durable. On worktree-creation failure, inspect and
   record partial state, then either cleanly release an unchanged guard or
   preserve it with the recovery token and phase.

   Takeover requires `--takeover` in an explicit current-prompt request. Show
   the prior owner and age first. Acquire the common-dir guard, re-read the
   owner, and stop if it differs from the owner the human authorized replacing.
   Only then replace the private Git-dir `owner.json` before releasing the
   guard.
   Never refresh, delete, or overwrite another owner's lock merely because the
   directory already exists.

7. **Copy `.claude/settings.local.json`** from the
   main repo into the worktree's `.claude/` dir so
   tool permissions carry over.

8. **Fixturize** (if requested):
   ```sh
   cd <repo-root>/wkts/<name>
   UV_PROJECT_ENVIRONMENT=.venv uv sync
   ```

9. **Switch working directory** to the worktree.

## Re-entry protocol

If `/open-wkt <name>` is called and `<repo-root>/wkts/<name>/` exists:

1. Verify the git worktree is still valid
   and require `git worktree list --porcelain` to map the exact absolute
   canonical path to the exact branch recorded in metadata. Require
   `wkt/<name>` unless `branch_exception: true` records a guarded legacy
   migration. Reject a symlinked destination or path escape before reading
   metadata.
2. Resolve and read `<worktree-git-dir>/ai-skillz-wkt/owner.json`, then compare
   its exact token with the current owner token.
3. If the tokens differ, stop. Re-entry is allowed only after an explicit
   `--takeover` request records the ownership transfer.
4. If the tokens match, preserve the lock and switch to the worktree.

## Legacy path migration

Run this section only after an explicit current-prompt `--migrate-legacy`
request for the exact name.

1. Resolve the repository root, registered legacy path
   `<repo-root>/.claude/wkts/<name>`, and new canonical path
   `<repo-root>/wkts/<name>`. Reject symlinks, path escapes, an occupied new
   path, or any registration mismatch.
2. Verify the legacy private-Git-dir metadata and exact owner token. A
   different or missing owner requires the normal explicit takeover/recovery
   contract before migration.
3. Acquire the common-Git-dir `<name>.guard`, re-read registration and owner,
   and record phase `migrating`, old path, new path, branch, and owner.
4. Run `git worktree move <legacy-absolute-path> <new-absolute-path>` while
   holding the guard. Verify registration, metadata, index, HEAD, and status at
   the new path.
5. Update `meta.json` with the canonical path and migration timestamp, then
   set `branch_exception: true` only when the validated registered branch is
   not `wkt/<name>`; otherwise record `false`. This exception records an
   existing migrated branch and never authorizes branch renaming or arbitrary
   path registration. Release the guard. Remove `claude_wkts` only when it resolves exactly to
   `.claude/wkts` and no registered worktrees remain beneath that legacy root.
   After verifying no files or registrations remain, remove the empty real
   `.claude/wkts` directory. Do not remove it when files or registrations
   remain, and never follow or recursively delete a legacy-root symlink.
6. Report the move. Future re-entry and teardown use only `wkts/<name>`.

### Interrupted migration recovery

When `--recover-guard <token>` finds phase `migrating`, validate the recorded
old path, new path, branch, owner, and both current registrations before any
mutation. If Git already registered the new path, finish post-move validation
and metadata update, then release the guard. If only the old path remains,
report that no move completed and release the unchanged guard. If both or
neither path is registered, stop and preserve the guard with an exact state
report; rollback or filesystem deletion requires a separate explicit request.

## Listing worktrees

`/open-wkt --list` (or `/ls-wkts` alias):

```
NAME                  BRANCH                   STATUS   AGE
fix_sigint_timeout    wkt/fix_sigint_timeout   active   2h
pr366_review          wkt/pr366_review         idle     1d
proto_wkt_skill       wkt/proto_wkt_skill      active   5m
```

Status is derived from the ownership directory and its recorded acquisition
time. A stale age is displayed but never treated as an unlocked state.

## Subagent usage

When a `Task` agent needs an isolated worktree:

1. The parent agent calls `/open-wkt <name>` with
   `--notify-on-teardown=false`.
2. Spawns the subagent with cwd set to the worktree.
3. On subagent completion, calls `/close-wkt <name>`.

The common-dir guard and private Git-dir owner record prevent concurrent
mutation without dirtying the worktree. Pass the same owner token to
`/close-wkt`; a different session must request an explicit takeover before
teardown.

## Files managed

```
<repo>/
├── wkts/
│   ├── <name>/                      # the worktree
│   │   ├── .claude/
│   │   │   └── settings.local.json
│   │   └── ...                      # repo contents
│   └── <another_name>/
└── .gitignore                       # includes wkts
```

Each linked worktree's private Git directory contains
`ai-skillz-wkt/meta.json` and `ai-skillz-wkt/owner.json`. The repository common
Git directory contains only short-lived `ai-skillz-wkt-locks/*.guard`
directories.

## .gitignore entries

Ensure these patterns exist in the repo's root
`.gitignore` (add if missing):

```
/wkts/
```
