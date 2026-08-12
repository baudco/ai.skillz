---
name: git-mgmt
description: >
  Manage Git branches, worktrees, stacked PRs, divergence, rebases,
  restacks, pushes, and other history-changing operations safely. Use when
  inspecting or changing branch relationships, especially when stacked
  branches may be operated on concurrently.
compatibility: >
  Requires git CLI. Fresh forge inspection prefers the provider-neutral gish
  adapter, with explicit direct-provider or local-only fallbacks. Conflict
  resolution uses the resolve-conflicts companion skill.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[branch, worktree, PR, or requested git operation]"
disable-model-invocation: false
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(bash *)
  - Read
  - Glob
  - Grep
---

# Git Management

Treat branch history as coordinated shared state, not as an implementation
detail an agent may rearrange for convenience.

The central invariant is:

> Inspect and report branch relationships proactively. Never initiate,
> propose, or ask to perform a rebase or restack unless the user explicitly
> requests that operation in the current prompt.

This distinction is critical for stacked branches. An upstream branch may be
under active development in another worktree while a downstream branch is
also changing. Its current tip is not necessarily a stable integration point.

## 1. Classify the requested operation

Separate observation from mutation before running commands.

Observation includes:

- inspect status, logs, ancestry, merge bases, worktrees and conflicts;
- compare local branches, remote-tracking refs and forge PR metadata;
- report that a base advanced or branches diverged;
- prepare a command or merge/rebase plan without executing it.

Mutation includes:

- rebase or restack;
- merge or cherry-pick;
- reset, branch deletion or branch retargeting;
- commit, amend or history rewrite;
- push, force-push or PR base/head changes;
- aborting or continuing an in-progress Git operation.

Authorization is operation-specific. A request to inspect, review, plan,
choose a likely base, or explain divergence does not authorize mutation.

## 2. Stacked-branch coordination rule

For stacked branches and PRs, assume every layer may be operated on
concurrently unless the user says otherwise.

Never do any of the following without an explicit current-prompt request to
rebase or restack:

- suggest a rebase/restack as the next step;
- ask whether the user wants a rebase/restack;
- infer permission from the user selecting or naming a base commit;
- start a rebase merely because the upstream branch advanced;
- move a downstream branch onto an intermediate local or remote tip.

Why this is load-bearing:

- the upstream tip may contain incomplete or temporary commits;
- concurrent work may add more commits before the stack is ready;
- early restacks create duplicate conflict-resolution work;
- rebases invalidate reviewed hashes, links and PR comment references;
- force-pushes can disrupt another worktree or collaborator;
- transient divergence can make forge PR diffs misleading.

When a stacked base changes, report the exact old and new refs as facts. Keep
working on non-history-mutating tasks when possible. If progress is blocked,
state the blocker and leave branch coordination to the human.

## 3. Refresh authoritative state

Do not infer current PR relationships from branch names or stale conversation
context.

For a forge PR/MR/patch request:

1. Query the forge for its current head ref, head SHA, base ref and base SHA.
2. Resolve related stacked PR metadata when the user identifies another PR as
   the base layer.
3. Compare forge SHAs with local branch and remote-tracking refs.
4. Label each value clearly as forge-reported, local or remote-tracking.
5. Prefer `/gish inspect-pr <backend> <num> --repo <owner/name>` as the
   provider-neutral forge adapter. Network access requires explicit
   authorization in the current prompt; loading a workflow which wants fresh
   metadata does not authorize it.
6. Require the adapter result to identify the provider, repository, PR, query
   time, head repository, head ref, head OID, base ref, and base-tip OID.
   Record a provider diff base OID only when the provider reports one; never
   derive it silently.
7. Compute and record the local merge-base OID separately. State every exact
   two-dot or three-dot range used for logs or diffs.
8. Verify any same-named local or remote-tracking ref against the corresponding
   forge OID before using that ref. Prefer verified OIDs in range commands.

Before using a modden-backed `gish` transport, resolve the deployed sibling
skill from the active provider root and run:

```text
../gish/scripts/gish-xontrib --check
```

Do not infer readiness from `$SHELL`, `PATH`, or an activated venv. The coding
harness shell and the backend environment are separate. The launcher selects
an explicitly configured absolute xonsh path and verifies the modden xontrib
under `--no-rc`. If it reports that no runtime is configured, describe the
setup in `../gish/DEPLOY.md`; do not choose or persist an interpreter without
the user's approval.

If the user prefers not to use `gish`, use a direct provider CLI or API only
when the selected provider can return every required field and the current
prompt explicitly authorizes that exact network read. Label the result as a
direct `<provider>` query rather than provider-neutral `gish` output. Never
silently switch transports for a remote write or for an operation whose safety
contract requires `gish`.

If `gish`, a complete approved direct adapter, network authorization, or
required metadata is unavailable, do not claim current forge authority.
Continue only with clearly labeled "local/prospective inspection at SHA
`<oid>`", state the local refs and exact range used, and report which forge
fields remain unverified. Do not fetch or ask to fetch as part of this
fallback.

The forge-reported PR head and base-tip OIDs are authoritative identities for
the submitted PR. They are not interchangeable with the local merge base or a
provider-reported diff base. A local worktree branch is authoritative only for
explicitly requested local or prospective inspection.

Remote-tracking refs are cached observations. Never call them current merely
because their names match the forge branches.

## 4. Worktree and branch ownership

Before any explicitly requested history mutation, inspect:

```text
git status --short --branch
git worktree list --porcelain
git branch --all --contains <relevant-sha>
git merge-base <base> <head>
git rev-list --left-right --count <base>...<head>
```

Confirm:

- the active worktree and checked-out branch;
- whether the index or tracked worktree is dirty;
- whether a merge, rebase or cherry-pick is already active;
- whether the target branch is checked out in another worktree;
- the exact old base, new base and branch tip SHAs;
- whether untracked paths would be overwritten.

Never switch, reset, delete or rewrite a branch checked out in another
worktree. Use its ref for read-only comparisons and let its owning worktree or
human coordinate mutations.

## 5. Explicit mutation authorization

Require the requested verb and target to be unambiguous.

These requests authorize execution after safety checks:

- "rebase `<branch>` onto `<base>`";
- "restack this branch onto `<sha>`";
- "abort the current rebase";
- "continue the rebase after resolving this conflict";
- "push this branch to `<remote>/<ref>`".

These requests do not authorize execution:

- "what should happen next?";
- "which branch is the base?";
- "check whether the base moved";
- "review this PR against PR N";
- selecting a base from choices offered during an unrelated workflow;
- "prepare a rebase plan".

A rebase request does not authorize a push. A push request does not authorize
a force-push. A conflict-resolution request does not authorize staging or
continuing unless the active conflict workflow explicitly allows it.

## 6. Rebase and restack protocol

Apply this section only after explicit authorization.

1. Re-read status, worktree ownership and authoritative refs immediately
   before mutation.
2. State the exact commit range and command to be executed.
3. Preserve unrelated staged, unstaged and untracked work.
4. Do not stash, reset, clean or force-checkout implicitly.
5. Start only the requested operation.
6. On conflict, stop. If `/resolve-conflicts` is deployed, hand off the exact
   operation and its current-prompt authorization provenance. If unavailable,
   report the missing companion and leave the conflict untouched.
7. Do not broaden the operation to another stacked branch.
8. After success, report old and new head SHAs and whether hashes changed.
9. Do not push or update forge metadata without separate authorization.

If a rebase/restack was started without explicit authorization, stop without
continuing, aborting, staging, or editing conflicts. Inspect and report the
operation and preserved state. Aborting is a separate mutation: require an
explicit current-prompt request to abort before doing so, then verify
restoration of the original head, index, and worktree.

## 7. Commit, push and forge boundaries

Treat these as separate human decisions:

- creating commits;
- rewriting commits;
- pushing a fast-forward branch;
- force-pushing rewritten history;
- changing a PR base or head;
- refreshing a PR description;
- posting review replies.

Do not chain them merely because one preceding action was approved. In stacked
workflows, batching PR messages and review links after the stack settles often
avoids stale hashes, but the human owns when that stable point has arrived.

## 8. Communication contract

Use precise state language:

- "Forge base-tip OID is `<sha>`; local merge-base OID is `<sha>`."
- "Provider diff base is unavailable; this is not inferred from the base tip."
- "The base advanced by N commits; no history was changed."
- "Commit inspection used `<base-tip>..<head>`; diff inspection used
  `<base-tip>...<head>`."
- "Local/prospective inspection at SHA `<head>` used `<base>...<head>`; forge
  head and base were not verified."
- "The branch is blocked on human-coordinated stack state."

Avoid directive language such as "next, rebase" unless the user explicitly
requested rebase planning. Never convert an observed divergence into implied
permission to rewrite history.
