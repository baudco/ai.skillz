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
- repository/worktree detection from the current invocation;
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
tree, staged path set, `git ls-files --stage --debug` output and exact digest of
the worktree-specific Git index. Record when the index file was initially
absent. The index may be empty; unlike a normal `/commit-msg` invocation, that
does not block planning when worktree changes exist.

Never rewrite the user's real index while generating a plan. Materialize each
boundary in a worktree-private temporary index initialized from its evidenced
parent tree, then apply the exact cached boundary patch there. Run staged diff
inspection with `GIT_INDEX_FILE` naming that temporary index. Remove temporary
indexes only after their boundary evidence and message archives are complete,
and verify the real index digest and stage metadata stayed unchanged.

Never use `git reset --hard`, `git clean`, automatic stash, checkout-based
discard, or any command that overwrites worktree content. Preserve unrelated
staged entries and user changes.

If exact boundaries require partial-file staging, use deterministic cached
patches or equivalent non-interactive index plumbing. Do not use an interactive
patch console. Store any generated planning or execution helper beneath the
ignored `commit-msg/msgs/` runtime directory and reference execution helpers
explicitly in the final command sequence.

## 4. Materialize Every Boundary

Resolve the repository's project-check command catalog once per plan, before
the boundary loop. Use only a repository-owned run-tests harness reference,
documented project commands and CI/build configuration already in the current
repository. Do not repeat that repository inspection for each boundary. Select
from the catalog for each boundary; do not rediscover equivalent commands.

For each planned commit, in dependency order:

1. Materialize that commit's exact boundary in its temporary index.
2. Compare the temporary index with that boundary's recorded parent tree for
   `git diff --cached --check`, statistics and name/status inspection. Never
   compare a later boundary with live `HEAD` or include preceding boundaries.
3. Read that same parent-relative staged diff and apply `/commit-msg`'s normal
   analysis.
4. Select required lint and targeted-test commands for that boundary. Assign
   the full suite once, against the final boundary tree, unless repository
   evidence explicitly requires an earlier boundary to run it independently.
   Do not execute project checks while generating the plan by default. Include
   pending checks in the human execution sequence. Run a project check during
   planning only when the user explicitly requests pre-execution, always
   against the exact boundary tree. Record a successful unchanged result and
   omit that check from the execution sequence rather than running it twice.
5. Generate a distinct project-style message from that exact boundary.
6. Archive it beneath `.claude/skills/commit-msg/msgs/` using the
   `commit-msg` naming convention. Add a zero-padded boundary ordinal when the
   timestamp and unchanged HEAD would otherwise produce a duplicate path.
7. Record the exact staging transition needed after the preceding commit.

Do not defer message generation or tell the human to rerun `/commit-msg` after
each commit. If any boundary cannot be safely materialized or verified, stop
and report the blocker instead of returning a partial plan.

## 5. Verify The Starting Index

After all boundaries and messages are verified, confirm that the untouched real
index still has its initial digest, tree, staged paths, stage/debug metadata and
staged diff. A mismatch means another writer changed it; preserve that state
and stop rather than restoring stale bytes.

Message archives, ignored cached patches and generated execution helpers may
remain. Remove planning indexes. Do not stage runtime artifacts unless they are
intended provenance files in a planned commit.

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
- required lint and targeted-test commands against each exact boundary tree;
- the full suite once against the final boundary tree, except where documented
  repository evidence requires an earlier independent run;
- `git diff --staged` immediately before every commit command so the human can
  review the exact staged patch at the final pre-commit gate;
- `git commit --edit --file
  .claude/skills/commit-msg/msgs/<generated-file>` for every commit.

For every pending project check, render a generated helper that first verifies
the current staged tree equals the recorded boundary tree, materializes that
tree in an isolated temporary checkout, runs the command there and removes the
checkout. Later-boundary or unrelated live-worktree content must not affect the
result. Do not render checks already pre-executed successfully against
unchanged boundary evidence.

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
- lightweight structural boundary checks and their outcomes are recorded;
- project-check commands were resolved once per repository;
- each required targeted check is rendered against its exact boundary and the
  full suite appears only at the final boundary unless documented otherwise;
- project checks are recorded as pending unless pre-executed against unchanged
  boundary evidence, in which case their outcomes are recorded and they are
  not rendered again;
- the index matches its initial tree;
- one shell-correct command block covers the complete sequence;
- the command block starts in the exact absolute repository/worktree root;
- every commit command includes `--edit`;
- every commit command is immediately preceded by `git diff --staged`;
- every non-final commit command is followed by exactly one blank line, while
  the final commit has no required trailing blank line;
- no command commits automatically before the editor opens;
- no push appears unless the human separately requests a push plan.

If any item is false, the commit plan is incomplete and must not be presented
as ready.

## 8. Report

State the exact repository/worktree root and branch first. List each commit in
order with its subject and scope, then provide the one shell-specific command
block. Mention excluded changes, checks already run, checks that remain for
execution time, and verification that the real index remained unchanged.

Do not repeat full commit-message bodies in chat unless the human requests
them. The archived files are the reviewable source for each message.
