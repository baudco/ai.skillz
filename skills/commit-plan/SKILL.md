---
name: commit-plan
description: >
  Build complete, ready-to-run multi-commit plans with exact boundaries,
  project-style messages, checks, and shell-correct commands. Use when the
  user says "commit plan", "multi-commit plan", or asks to split changes into
  commits. Requires the `commit-msg` and `run-tests` skills.
compatibility: >
  Requires git CLI, deployed commit-msg and run-tests skills, and a known
  command parser.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[optional-scope-or-boundary-guidance]"
---

# Commit Plan

Create a complete commit package by composing with the
`commit-msg` skill.
Use the current harness's skill invocation syntax: `$commit-plan` in
Codex, `/commit-plan` in Claude Code or the OpenCode command adapter.
Planning authorizes temporary index changes and ignored message artifacts, not
commits, pushes, rebases, stashes, or worktree cleanup.

## 1. Load The Dependencies

Resolve and read the `commit-msg` and `run-tests` skills advertised by
the current harness before inspecting changes. Use each skill's
advertised resource path when available. Otherwise check the current
repository's `.agents/skills/`,
then the active harness's `.claude/skills/` or `.opencode/skills/` deployment,
then exact global deployments advertised in the harness registry.
If definitions disagree, resolve the ambiguity before proceeding. Resolve
relative resources against the loaded skill directory, not the working
directory. Do not scan `~`, sibling repositories, or arbitrary external roots.

`commit-msg` owns:

- the no-auto-commit and mandatory `--edit` rules;
- repository/worktree detection from the current invocation;
- staged-diff analysis and project message style;
- review/regression context and Prompt-IO trailers;
- archived and latest message file locations;
- commit-message footers and post-commit follow-up.

`run-tests` owns project environment wrappers, safe test scopes,
authorization-required exclusions, process-isolation rules, command ordering
and known outcomes. Its repository-local harness reference is optional; use its
documented conservative fallback when one is absent.

This skill owns multi-boundary orchestration. When reading `commit-msg`, ignore
only its **"COMMIT PLAN" compatibility redirect**; following that redirect
would recurse back into this already-active skill. Apply every other relevant
`commit-msg` rule.

If either trusted dependency is unavailable, stop and give the canonical
deployment command. Never invent message conventions, test commands, package
names, environments or known outcomes.

## 2. Interpret The Request

The literal phrase **"commit plan"** (case-insensitive), a request to
split changes, or an explicit `commit-plan` skill invocation requests
a complete, ready-to-run commit package, not merely proposed subjects
or boundaries.

Honor human-specified boundaries first. Otherwise inspect the
complete staged, unstaged, and untracked change set and choose the
fewest atomic, dependency-ordered commits that keep tests and
contracts coherent. A one-boundary plan is correct when all changes
form one atomic commit. Do not split tightly coupled production and
test changes merely to increase the count.

Ask one short question only when two materially different valid
boundaries cannot be resolved from repository evidence.

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

Generate a deterministic cached patch for every boundary, including whole-file
boundaries. Do not use an interactive patch console. Store patches and one
JSON execution specification beneath the ignored `commit-msg/msgs/` runtime
directory. Pin the specification and every patch and message artifact by
SHA-256. Use full canonical object IDs for the repository's object format.

Use the deployed `scripts/plan-exec.py` executor; do not generate a competing
state machine. The standalone specification records:

- canonical repository root, common Git directory, worktree Git directory,
  branch ref, initial parent/tree and initial index tree;
- consecutive boundaries with their subject, parent/result trees and expected
  pre-staging index tree;
- one role-bound patch and archived message with SHA-256 digests;
- ordered project-check command objects selected through `/run-tests`, each
  with an argument vector, explicit environment overlay and a source-resolution
  probe executed under that same environment.

The executor owns patch application, structural checks, exact-tree project
check isolation, staged review, the editor-backed commit command, boundary
ordering, completion detection and divergence refusal. Generated commands may
not replace those operations.

Record relative project executables only when they are executable files in the
boundary tree. Resolve ignored repository-local tools, including virtual
environment entry points, to absolute paths. For Python projects, include the
documented import-resolution probe with every distinct interpreter/environment
and require the imported package path to remain beneath
`AI_SKILLZ_BOUNDARY_ROOT`.

## 4. Materialize Every Boundary

Resolve the repository's project-check catalog once per plan, before the
boundary loop. Use the loaded `/run-tests` contract and its repository-local
harness reference as authoritative. Use project or CI documentation only where
that authority is silent. Do not rediscover, merge or broaden commands per
boundary.

For each planned commit, in dependency order:

1. Materialize that commit's exact boundary in its temporary index.
2. Compare the temporary index with that boundary's recorded parent tree for
   `git diff --cached --check`, statistics and name/status inspection. Never
   compare a later boundary with live `HEAD` or include preceding boundaries.
3. Read that same parent-relative staged diff and apply `/commit-msg`'s normal
   analysis.
4. Select required lint and targeted-test commands for that boundary. Assign
   the broadest repository-documented safe regression sequence, when one
   exists, once against the final boundary tree. A literal test-root run is
   allowed only when `/run-tests` classifies it as safe; never synthesize one
   or include authorization-required coverage implicitly. Do not execute
   project checks while planning unless the user requests it. Include pending
   checks in the execution sequence. Record a successful unchanged result and
   omit that check rather than running it twice.
5. Generate a distinct project-style message from that exact boundary.
6. Archive it beneath `.claude/skills/commit-msg/msgs/` using the
   `commit-msg` naming convention. Add a zero-padded boundary ordinal when the
   timestamp and unchanged HEAD would otherwise produce a duplicate path.
7. Record the exact staging transition needed after the preceding commit.
8. Add the boundary and its immutable evidence to the execution specification.

Do not defer message generation or tell the human to rerun `/commit-msg` after
each commit. If any boundary cannot be safely materialized or verified, stop
and report the blocker instead of returning a partial plan.

## 5. Verify The Starting Index

After all boundaries and messages are verified, confirm that the untouched real
index still has its initial digest, tree, staged paths, stage/debug metadata and
staged diff. A mismatch means another writer changed it; preserve that state
and stop rather than restoring stale bytes.

Message archives, ignored cached patches and execution specifications may
remain. Remove planning indexes. Do not stage runtime artifacts unless they
are intended provenance files in a planned commit.

## 6. Render For The User's Shell

Choose the active command parser from evidence in this order:

1. an explicit parser or shell selected by the user for this command block;
2. harness-reported command parser metadata from the active provider session;
3. parser semantics already demonstrated by commands in the current session;
4. the actual parent/ancestor interpreter from process metadata or an
   equivalent provider diagnostic;
5. the basename of `$SHELL`, only as a last-resort hint.

Do not equate inherited login-shell metadata with the active parser. Report
conflicting signals and which higher-priority evidence won. If equal-priority
evidence remains ambiguous, ask which parser to target.

Render every command on one physical line. Never use newline continuations,
undeclared Python names or one-shot `assert` preconditions.

Use one explicitly labelled fence and valid syntax for the selected parser.
Never emit an unlabelled fence or hardcode syntax for another parser. With
startup files disabled where supported, parse every fence line and validate
the specification without executing it. Then run only
the selected Python interpreter with `plan-exec.py --preflight`.
Preflight authenticates artifacts and inspects
required executables without running resolution or import probes. Those
probes run during `--execute` in the isolated boundary tree. Preflight must
not stage, run project checks, invoke an editor or commit, access the
network or enter normal execution.

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

The executor asset is a non-executable Python source file. Every mode must
invoke it through an explicit interpreter, for example:

```xsh
python3 <skill-dir>/scripts/plan-exec.py --spec <plan.json> --sha256 <digest> --preflight
```

Use the selected interpreter and quote paths for the user's shell.
Never render a bare `plan-exec.py --<mode>` as a runnable command.
The command block must include, in execution order:

- one interpreter-backed `--preflight` invocation naming the specification
  and digest;
- one interpreter-backed `--show` invocation rendering every project
  check, `git diff --staged` review and `git commit --edit --file`
  operation as a plain command alongside the pinned patch;
- one interpreter-backed `--execute <ordinal>` invocation per
  boundary, naming the same specification and digest.

The executor applies the authenticated patch, then runs staged whitespace,
statistics and path checks before every commit. Only Git's internal diff
implementation is used for index comparisons,
structural checks and staged review; external diff drivers and text
conversion are disabled so they cannot run code during validation.

The specification includes required lint and targeted tests against
each exact boundary tree and the
broadest documented safe regression sequence once against the final boundary
tree when one exists. The executor runs `git diff --staged` immediately before
constructing the only permitted commit form:
`git commit --edit --file <authenticated-message-snapshot>`.

Preview and execution must use the same command descriptions. `--show`
renders the exact argv and an isolated-tree cwd placeholder before anything
executes. It may show authenticated environment variable names, but must hide
their values and the inherited environment. `--execute` announces each
boundary phase, cwd and command immediately before running it, then reports
`PASS`, `SKIP` or `FAIL exit=<status>`. For captured automated operations,
preserve stdout and stderr on failure, but
escape terminal controls and redact authenticated and inherited
environment values. Editor and hook output are trusted, not captured.
The human must be able to identify the failing
check without reconstructing hidden subprocess state.

The executor verifies the staged tree, then materializes every pending project
check boundary by making a shared, no-checkout clone in a temporary project
root. It adds the boundary tree as a synthetic commit whose parent is the
actual pending parent, preserving local history and refs while keeping Git
metadata independent. It requires `git rev-parse --show-toplevel` and
`--git-dir` to resolve inside that root, never a containing repository.
Preserve every documented environment wrapper and fresh-process boundary in
the specification; exclude separately tested or state-leaking tiers from a
later broad process. The executor clears ambient Python path overrides, and
the import check must reject an editable install resolving outside the
temporary root. The executor removes the root afterward. Do not include checks
already passed against unchanged boundary evidence.

For each `--execute` call, the canonical executor walks backward from `HEAD`
to the recorded initial parent. Each intervening commit must have exactly one
parent and the corresponding recorded boundary tree. It rejects ambient Git
repository/index redirection and ignores replacement refs. It then:

- exits successfully before staging, checks, review, editor or hooks when that
  boundary is already complete;
- executes only the first pending boundary and refuses a later one;
- accepts either the recorded pre-staging index or exact result tree, applies
  the pinned patch to a private index under the real index lock only when
  needed, then publishes and verifies the result tree under that lock;
- runs structural and isolated project checks fail-fast, then staged review
  and its fixed editor-backed commit as one boundary operation;
- gives each pending project check and its resolution probe a fresh
  exact-tree clone, so generated files from one check cannot influence
  another check's result; tracked mutations within a check still refuse;
- after staged review, locks the real index and checks its planned tree;
  the editor and hooks run in an owned detached checkout. Publish its
  exact-parent/tree commit only by a compare-and-swap of the recorded
  branch ref while its worktree's symbolic `HEAD` is locked. Run the
  update from the detached checkout to keep its `HEAD` separate,
  leaving the already-staged exact real-index tree untouched;
- after the editor or hooks return, accepts completion only when the new commit
  has the exact expected parent/tree relationship;
- leaves an editor-aborted boundary pending and safe to execute again;
- refuses extra, merge, reordered or tree-mismatched commits as divergence.

An editor abort leaves the staged boundary pending and removes the lock.
If `HEAD` advances outside the planned tree, the private index is retained
for manual recovery; do not rewrite the real index to hide that state.
Hooks that change the detached commit's parent/tree prevent publication
and retain its checkout for manual recovery. Process death between ref
publication and lock release can leave a stale index or `HEAD` lock,
but the real index already contains the exact committed tree.
Inspect owned recovery artifacts before releasing a stale lock;
never reset the real index or claim crash-atomic execution.

Commit OIDs and message text may differ because the editor may change the
message; parent and complete tree identity define completion. Once all exact
boundaries are committed, every `--execute` line is a successful no-op. This
must remain true after a partial run and when unrelated staged changes are
added after full completion.

Use each archived message path directly as its boundary's role-bound message.
Never use `.claude/git_commit_msg_LATEST.md` in a multi-commit sequence because
later message generation overwrites it. The executor authenticates that file
once and passes an immutable snapshot to `git commit --edit --file`.

Visually separate boundary executor calls inside the command fence. Emit
exactly one blank line after every non-final `--execute` command. The final
executor call normally terminates the fence, so do not require or add a
trailing blank line after it.

Keep `git diff --staged` as an intentional human review gate even when the
earlier summary and path checks passed. The executor displays its sanitized
diff directly and does not run a configured external pager. In an interactive
terminal, pressing Enter after reviewing continues; Ctrl-C or another answer
aborts before commit. The editor-backed `git commit --edit --file` and local
hooks inherit the user's terminal. Their output is trusted and not redacted,
unlike captured automated-check and Git diagnostic output. A completed
boundary skips the review and editor entirely.

## 7. Completion Gate

Before returning a finished plan, verify:

- every changed path belongs to one planned commit or is explicitly excluded;
- every commit has one archived message generated from its exact staged diff;
- every boundary is atomic and ordered after its dependencies;
- the pinned specification is schema-valid and every artifact digest matches;
- the executor recognizes completion only from an exact single-parent tree
  chain and refuses every other `HEAD` relationship;
- lightweight structural boundary checks and their outcomes are recorded;
- project-check commands were resolved once per repository;
- each required targeted check is rendered against its exact boundary and the
  documented broad safe sequence appears only at the final boundary, when one
  exists;
- project checks are recorded as pending unless pre-executed against unchanged
  boundary evidence, in which case their outcomes are recorded and they are
  not rendered again;
- the index matches its initial tree;
- one shell-correct command block covers the complete sequence;
- parser evidence follows the documented hierarchy and conflicts are reported;
- every fence line and specification passes no-startup validation, and
  preflight is read-only and cannot enter normal execution;
- the command block starts in the exact absolute repository/worktree root;
- every boundary binds one archived message and the executor constructs only
  `git commit --edit --file <authenticated-message-snapshot>`;
- the executor runs `git diff --staged` immediately before that commit;
- the complete sequence succeeds after partial or complete execution without
  rerunning completed checks, editors, hooks or commits;
- every non-final executor call is followed by exactly one blank line, while
  the final call has no required trailing blank line;
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
