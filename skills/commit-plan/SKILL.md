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
checks/outcomes, dependency IDs, assigned review-reply IDs and completion
state. Assign each pending reply to exactly one stable boundary using review
context and changed-path evidence. Ask when ownership is ambiguous; never let
the first new `HEAD` consume replies owned by later boundaries.

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

Generate deterministic cached patches and a per-boundary execution helper
beneath the ignored `commit-msg/msgs/` runtime directory for every plan, not
only partial-file boundaries. Do not use an interactive patch console. The
helper must construct a private boundary index from the evidenced parent tree
and apply the exact cached patch there; it must never depend on the user's
current staged state. Reference it explicitly in the final command sequence.

The helper must support idempotent `ensure` and `run -- <command>` operations:

- recognize an already completed boundary from the recorded parent/tree chain,
  print a concise skip notice and exit successfully;
- otherwise require the evidenced parent relationship, recreate the private
  index from that parent and apply/verify the recorded patch and staged tree;
- populate an isolated execution root from the verified private index, then
  execute every `run` command from that root with `GIT_DIR` naming the active
  worktree's private Git directory, `GIT_WORK_TREE` naming the isolated root and
  `GIT_INDEX_FILE` naming the private index. Checks, editors and hooks must not
  read later-boundary or unrelated live-worktree content;
- reject unexpected `HEAD`, parent, patch, tree or message-digest changes
  instead of guessing, duplicating a commit or overwriting worktree content;
- before invoking the editor, durably journal the boundary ID, expected
  parent/tree, patch and message digests, helper writer token, pointer/receipt
  digests, real-index path/digest and exact stage entries, and phase;
- after a successful wrapped commit, verify its parent/tree and reconcile the
  real index with a temporary three-way transition using the expected parent as
  base, the committed tree as the new base and the execution-time real index as
  user state. Atomically install it only if the real-index digest still matches;
  preserve all non-boundary and non-overlapping staged changes and all worktree
  content. On overlap or compare-and-swap failure, leave the real index bytes
  untouched and report the required reconciliation instead of replacing whole
  entries by path;
- make interruption before, during or after the editor safe to rerun. A helper
  rerun must either resume the same pending boundary or recognize its exact
  committed tree; it must never create a second commit for it.

The durable journal authorizes the helper to resume only its own matching
pointer/receipt transaction under `/git-mgmt`'s writer-continuation rule. On
rerun after `HEAD` advanced, classify before doing anything else:

- expected parent and tree: finish index reconciliation, receipt publication
  and completion recording, then return successful already-complete no-ops;
- expected parent but a different committed tree, including hook-modified
  private-index content: record `diverged-after-commit`, never commit again and
  stop for replanning;
- any unrelated parent/ancestry change: stop without staging or committing.

Hook-modified or unrelated commits are necessary errors, not idempotent skips.
Message-only editor or hook changes remain valid because completion is based on
parent/tree relationships rather than the final commit OID or message text.

## 4. Materialize Every Boundary

Materialize every boundary on an initial plan. On an invalidated plan,
materialize every affected boundary and its transitive dependants. For an
unchanged refresh, first compare the receipt's evidenced base OID, task/scope,
scoped content, starting index-stage/cached-patch digests and every archived
message digest. If they all match, reuse the exact boundaries, checks and
messages without staging them again. Only update relocatable worktree roots in
the receipt and rendered commands.

When boundary materialization or check selection is required, do the following.
Resolve the repository's project-check command catalog once per plan, before
the boundary loop. Use only a repository-owned run-tests harness reference,
documented project commands and CI/build configuration already in the current
repository. Do not repeat that repository inspection for each boundary. Select
from the catalog for each boundary; do not rediscover equivalent commands.

For each planned commit, in dependency order:

1. Materialize that commit's exact boundary in its private execution index.
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
7. Record the exact helper transition needed after the preceding commit.
8. Record boundary-owned review replies and defer their candidate generation
   until that exact boundary's parent/tree completion is verified. Completion
   of another boundary must not consume them.

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

## 5. Verify The Starting Index

After all boundaries and messages are verified, confirm that the untouched real
index still has its initial digest, tree, staged paths, stage/debug metadata and
staged diff. A mismatch means another writer changed it; preserve that state
and stop rather than restoring stale bytes.

Message archives, execution journals, private indexes, generated helpers and
ignored cached patches may remain. Remove planning indexes after their evidence
is archived. Execution-time journal/index snapshots remain until their boundary
reaches a durable completed or explicitly divergent state. Do not stage runtime
artifacts unless they are intended provenance files in a planned commit.

## 6. Render For The User's Shell

Choose the active command parser from evidence in this order:

1. an explicit parser or shell selected by the user for this command block;
2. harness-reported command parser metadata from the active provider session;
3. parser semantics already demonstrated by successful or failed commands in
   the current session;
4. the actual parent/ancestor command interpreter reported by process metadata
   or an equivalent provider diagnostic;
5. the basename of `$SHELL`, only as a last-resort hint.

Do not equate inherited login-shell metadata with the active parser. In
particular, `$SHELL=sh` does not override harness or observed xonsh evidence.
Report every conflicting signal and which higher-priority evidence won. If
equal-priority evidence remains ambiguous, ask which parser to target before
rendering rather than silently choosing `$SHELL`.

Use the selected parser as the single Markdown fence language and command
syntax. Render every command on one physical line for every parser. Never use
a trailing `\` or any other newline-continuation syntax; pasted continuation
lines are parser-sensitive and can become separate or invalid commands.

Render environment overlays portably as `env KEY=value command` (and
`env KEY1=value1 KEY2=value2 command` for multiple values) in every shell.
Never emit a leading `KEY=value command` assignment or parser-specific
environment syntax. When the target is a shell builtin or function that
cannot run through `env`, put the overlay inside a generated helper or an
explicit parser subprocess instead.

The returned sequence must use one explicitly labelled fence and valid syntax
for the selected parser. Never emit an unlabelled fence or hardcode POSIX
syntax for a different parser.

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

- each boundary helper's `ensure` command, independent of the current index;
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

Wrap every per-boundary check, review and commit command as
`<boundary-helper> run -- <command>`. This keeps `git diff --staged` and the
mandatory `git commit --edit --file ...` visible in the rendered sequence while
running them against the exact private index and isolated execution root. Do not
render raw `git add`,
`git restore --staged`, `git reset` or `git apply --cached` commands whose
result depends on the caller's staged state. Every rendered line must succeed
as a no-op when its boundary is already complete, so the full command block can
be rerun after partial or complete execution without needless errors or
duplicate commits.

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
- every boundary helper reconstructs and verifies its private index without
  assuming the current staged state;
- lightweight structural boundary checks and their outcomes are recorded;
- project-check commands were resolved once per repository;
- each required targeted check is rendered against its exact boundary and the
  full suite appears only at the final boundary unless documented otherwise;
- project checks are recorded as pending unless pre-executed against unchanged
  boundary evidence, in which case their outcomes are recorded and they are
  not rendered again;
- the index matches its initial tree;
- one shell-correct command block covers the complete sequence;
- the fence parser follows the evidence hierarchy and any conflicting signals
  are reported;
- every rendered command occupies one physical line and every environment
  overlay uses `env` or a generated helper;
- the command block starts in the exact absolute repository/worktree root;
- every commit command includes `--edit`;
- every commit command is immediately preceded by `git diff --staged`;
- every check, review and commit is helper-wrapped and the complete command
  sequence is safe to rerun after any completed boundary;
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
execution time, and verification that the real index remained unchanged.

Do not repeat full commit-message bodies in chat unless the human requests
them. The archived files are the reviewable source for each message.
