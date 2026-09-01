---
name: commit-plan
description: >
  Build complete, ready-to-run multi-commit plans with exact boundaries,
  project-style messages, checks, and shell-correct commands. Use when the
  user says "commit plan", "multi-commit plan", or asks to split changes into
  commits. Requires the `commit-msg` skill.
compatibility: >
  Requires git CLI, a deployed commit-msg skill, and a known user shell.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[optional-scope-or-boundary-guidance]"
---

# Commit Plan

Create a complete multi-commit package by composing with `/commit-msg`.
Planning authorizes temporary index changes and ignored message artifacts, not
commits, pushes, rebases, stashes, or worktree cleanup.

## 1. Load The Dependency

Resolve and read the `commit-msg` skill advertised by the current harness
before inspecting changes. Prefer the current provider's project deployment,
then a safely resolved deployment from the other supported project provider,
then an exact global deployment already advertised in the harness skill
registry. Do not scan `~`, sibling repositories, or arbitrary external roots.

`commit-msg` owns:

- the no-auto-commit and mandatory `--edit` rules;
- repository/worktree detection and session tracking;
- staged-diff analysis and project message style;
- review/regression context and Prompt-IO trailers;
- archived and latest message file locations;
- commit-message footers and post-commit follow-up.

This skill owns multi-boundary orchestration. When reading `commit-msg`, ignore
only its **"COMMIT PLAN" compatibility redirect**; following that redirect
would recurse back into this already-active skill. Apply every other relevant
`commit-msg` rule.

If a trusted deployed `commit-msg` skill is unavailable, stop and give the
canonical deployment command. Never invent or copy another repository's
message conventions.

Before materializing boundaries, use `/git-mgmt` to read the fixed active-task
pointer, validate it against the changed paths, task terms and issue/PR
identifiers, then read only its exact-key policy receipt. Commit planning is
continuation work: never ask about or initiate discovery merely because the
pointer or receipt is missing, mismatched, declined, corrupt or approved but
pending. Reuse or narrowly refresh completed evidence only under an approved
policy. This authorizes no network access or Git mutation. If an approved scan
found equivalent work, preserve the index and stop before returning executable
commit commands.

For a plan refresh, load any worktree-private policy receipt before doing
expensive boundary work. Discovery may be absent or declined; that does not
block planning. A reusable commit-plan receipt must additionally
store a versioned `extensions.commit-plan` object. It records a stable plan ID,
starting index-stage/cached-patch digests and, for each stable boundary ID, the
repository identity, sorted path set, expected parent OID or prior-boundary ID,
expected parent tree, staged tree, patch digest relative to that parent,
pre/post-index fingerprints, archived message path/digest, exact
checks/outcomes, dependency IDs and completion state.

Every creation or mutation of `extensions.commit-plan`, including completion
updates after human commits, must use `/git-mgmt`'s pointer transaction: publish
`receipt_sha256: null`, atomically replace the receipt, then publish its new
digest. The pointer's scan policy remains authoritative throughout.

For a cross-repository plan, also write an ignored plan manifest beneath the
`commit-msg/msgs/` runtime directory. It maps the plan ID to canonical
repository IDs, receipt digests, boundary IDs and cross-repository dependency
edges. Validate repository receipts independently, then invalidate only the
changed repository's boundaries and their transitive dependants.

## 2. Interpret The Request

The literal phrase **"commit plan"** (case-insensitive), a request to split
changes into multiple commits, or an explicit `/commit-plan` invocation
requests a complete, ready-to-run multi-commit package, not merely proposed
subjects or boundaries.

Honor human-specified boundaries first. Otherwise inspect the complete staged,
unstaged, and untracked change set and choose the smallest set of atomic,
dependency-ordered commits that keeps tests and contracts coherent. Do not add
backward-compatibility commits or split tightly coupled production and test
changes solely to increase commit count.

Ask one short question only when two materially different valid boundaries
cannot be resolved from repository evidence.

## 3. Preserve The Starting Index

Refuse to plan while the index has unmerged entries. Record the initial index
tree, staged path set, and `git ls-files --stage --debug` output. Also save an
exact byte copy and digest of the worktree-specific Git index path beneath the
ignored `commit-msg/msgs/` runtime directory. Record when the index file was
initially absent. The index may be empty; unlike a normal `/commit-msg`
invocation, that does not block planning when worktree changes exist.

Never use `git reset --hard`, `git clean`, automatic stash, checkout-based
discard, or any command that overwrites worktree content. Preserve unrelated
staged entries and user changes.

If exact boundaries require partial-file staging, use deterministic cached
patches or equivalent non-interactive index plumbing. Do not use an interactive
patch console. Store any generated staging helper beneath the ignored
`commit-msg/msgs/` runtime directory and reference it explicitly in the final
command sequence.

## 4. Materialize Every Boundary

Materialize every boundary on an initial plan. On an invalidated plan,
materialize every affected boundary and its transitive dependants. For an
unchanged refresh, first compare the receipt's evidenced base OID, task/scope,
scoped content, starting index-stage/cached-patch digests and every archived
message digest. If they all match, reuse the exact boundaries, checks and
messages without staging them again. Only update relocatable worktree roots in
the receipt and rendered commands.

For each planned commit, in dependency order:

1. Materialize that commit's exact boundary in the index.
2. Run `git diff --cached --check`, statistics, and name/status inspection.
3. Read the staged diff and apply `/commit-msg`'s normal analysis.
4. Run required checks against the exact staged tree. When unstaged later
   changes would contaminate a check, construct a temporary detached worktree
   from the staged tree and remove it after verification.
5. Generate a distinct project-style message from that exact boundary.
6. Archive it beneath `.claude/skills/commit-msg/msgs/` using the
   `commit-msg` naming convention. Add a zero-padded boundary ordinal when the
   timestamp and unchanged HEAD would otherwise produce a duplicate path.
7. Record the exact staging transition needed after the preceding commit.

Do not defer message generation or tell the human to rerun `/commit-msg` after
each commit. If any boundary cannot be safely materialized or verified, stop
and report the blocker instead of returning a partial plan.

Invalidate work proportionally:

- root relocation only: update command paths;
- missing message: regenerate it from its unchanged recorded staged boundary,
  without repeating discovery or tests;
- changed message digest: preserve the human-owned file, report the mismatch
  and ask whether to use it or generate a separate candidate file;
- changed relevant ref/worktree: rerun `/git-mgmt` for that evidence first;
- changed content, scope, base or starting index: rematerialize and reverify
  affected boundaries and their transitive dependants, checks and messages;
- changed repository in a cross-repository plan: invalidate only that
  repository's receipt and dependent boundaries.

Ownership acquisition or transfer is a separate lifecycle concern. It neither
validates nor invalidates commit boundaries; check it independently before any
command that requires worktree ownership.

When refreshing after the human executed part of a plan, recognize completed
boundaries before applying normal invalidation. Walk first-parent commits from
the recorded initial parent through current `HEAD` and match boundaries in
order by parent relationship and committed tree, not commit OID or final
message text. For boundary 1, require its commit parent to equal the recorded
initial OID and its tree to equal the recorded staged tree. For each later
boundary, require its parent commit to be the commit matched to the prior
boundary and its tree to equal the recorded staged tree. This permits `--edit`
to change commit OIDs while proving exact content and order. Mark matched
boundaries completed, advance `discovery_head_oid`, and recompute baseline
index/content fingerprints for the remaining boundaries. Treat this
active-branch advancement as expected execution, not a new duplicate
candidate. Any nonmatching commit, tree or parent invalidates that boundary
and its transitive dependants.

## 5. Restore The Starting Index

After all boundaries and messages are verified, atomically restore the saved
index bytes, or restore initial index absence when applicable. Verify its
digest, tree, staged paths, stage/debug metadata, and staged diff before
presenting the plan. Remove the temporary index backup only after every check
matches.

Message archives and ignored cached patches may remain. Do not stage them
unless they are intended provenance files in a planned commit.

## 6. Render For The User's Shell

Determine the configured `$SHELL` and use its basename as the single Markdown
fence language and command syntax. Examples: `/bin/zsh` becomes `zsh`,
`/bin/bash` becomes `bash`, `/usr/bin/fish` becomes `fish`, and
`/usr/bin/xonsh` becomes `xonsh`.

For `xonsh`, render every command on one physical line. Never use a trailing
`\` or any other newline-continuation syntax: pasted continuation lines can
be parsed as indented Python instead of subprocess arguments. Keep a runnable
sequence as one command per line inside the same `xonsh` fence.

The returned sequence must use one explicitly labelled fence and valid syntax
for that shell. Never emit an unlabelled fence or hardcode POSIX syntax for a
different shell. If `$SHELL` is unavailable or unknown, ask which shell to
target before returning the plan.

Never assume the user's shell is already in the repository or worktree being
planned. The first command in the fence must change directory to the exact
absolute root returned by `git rev-parse --show-toplevel`. Render it as a
standalone shell-correct command, quoting the path when required; do not chain
it to the first staging command. When a plan intentionally spans repositories
or worktrees, emit another explicit directory-change command before each
boundary whose root differs.

Immediately before the command fence, state the exact repository/worktree
root and checked-out branch where the sequence applies. This is especially
important for linked worktrees whose branch and path differ from the caller's
original working directory.

The command block must include, in execution order:

- exact staging and unstaging commands for every boundary;
- staged whitespace, statistics, and path checks before every commit;
- required lint and test commands;
- `git diff --staged` immediately before every commit command so the human can
  review the exact staged patch at the final pre-commit gate;
- `git commit --edit --file
  .claude/skills/commit-msg/msgs/<generated-file>` for every commit.

Use each archived message path directly. Never use
`.claude/git_commit_msg_LATEST.md` in a multi-commit sequence because later
message generation overwrites it.

Visually separate commit boundaries inside the command fence. Emit exactly one
blank line after every non-final `git commit` command before the next commit's
staging sequence. The final `git commit` normally terminates the fence, so do
not require or add a trailing blank line after it.

Keep `git diff --staged` as an intentional human review gate even when the
earlier summary and path checks passed. It may open Git's pager; the human can
press `q` immediately to continue when they do not need to inspect the patch.

## 7. Completion Gate

Before returning a finished plan, verify:

- every changed path belongs to one planned commit or is explicitly excluded;
- every commit has one archived message generated from its exact staged diff;
- every boundary is atomic and ordered after its dependencies;
- exact-boundary checks and their outcomes are recorded;
- the index matches its initial tree;
- one shell-correct command block covers the complete sequence;
- the command block starts in the exact absolute repository/worktree root;
- every commit command includes `--edit`;
- every commit command is immediately preceded by `git diff --staged`;
- every non-final commit command is followed by exactly one blank line, while
  the final commit has no required trailing blank line;
- no command commits automatically before the editor opens;
- no push appears unless the human separately requests a push plan.

For an unchanged refresh, a valid receipt containing these exact outcomes
satisfies the checks already completed. Checks explicitly marked for execution
time remain in the rendered command sequence.

If any item is false, the commit plan is incomplete and must not be presented
as ready.

## 8. Report

State the exact repository/worktree root and branch first. List each commit in
order with its subject and scope, then provide the one shell-specific command
block. Mention excluded changes, checks already run, checks that remain for
execution time, and the restored index state.

Do not repeat full commit-message bodies in chat unless the human requests
them. The archived files are the reviewable source for each message.
