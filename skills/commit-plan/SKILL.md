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

## Repository configuration and runtime paths

Before accessing project guidance or workflow state, read and apply
[the shared runtime contract](../../docs/runtime-state.md#workflow-integration).
Resolve this link from the canonical `SKILL.md` location after
following its symlink. Reuse the resolved paths across composed skills.

Create a complete commit package by composing with the `commit-msg` and
`run-tests` skills.
Use the current harness's skill invocation syntax: `$commit-plan` in
Codex, `/commit-plan` in Claude Code or the OpenCode command adapter.
Planning authorizes temporary index changes and ignored message artifacts, not
commits, pushes, rebases, stashes, or worktree cleanup.

## 1. Load The Dependencies

Resolve and read the `commit-msg` and `run-tests` skills advertised by the
current harness before inspecting changes. Use their advertised resource paths
when available. Otherwise check the current repository's `.agents/skills/`,
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
JSON execution specification beneath the ignored `<commit_messages>/`
runtime directory. Pin the specification and every patch and message by
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
   checks in the execution sequence. Always retain selected commands under
   the user-facing Micro CI heading, including previously passed checks.
   Without reusable evidence, render RUN and execute as before.
5. Generate a distinct project-style message from that exact boundary.
6. Archive it beneath `<commit_messages>/` using the
   `commit-msg` naming convention. Add a zero-padded boundary ordinal when the
   timestamp and unchanged HEAD would otherwise produce a duplicate path.
7. Record the exact staging transition needed after the preceding commit.
8. Add the boundary and its immutable evidence to the execution specification.

Do not defer message generation or tell the human to rerun `/commit-msg` after
each commit. If any boundary cannot be safely materialized or verified, stop
and report the blocker instead of returning a partial plan.

An optional `prior_pass` object inside each `project_checks` command
records exactly `tree`, `source`, `outcome`, and integer `exit: 0`.
The tree must equal the boundary tree. The attributable source and
outcome summary must be non-empty, safe, non-secret strings. Embed
evidence only after the exact boundary tree, argv, environment overlay
and resolution probe in that same authenticated command object have
passed unchanged. Archive raw outputs and provenance in local runtime.
The specification digest binds that association; it is an attestation,
not independent verification of external tools or ambient environment.
Do not copy evidence when any of those inputs changes. No cache or
journal is involved. Absent evidence preserves v1 execution behavior;
malformed claimed reuse or a tree mismatch must fail closed. Failed or
unproven checks remain pending, with observations in the verification
report rather than claimed reuse. Never omit a selected passed check.
Render SKIP prior PASS with outcome and exit status; retain source
and tree evidence in the pinned specification/artifacts. Do not run
its probe/check, require its executable in preflight, or create a clone
solely for reused checks. Completed-boundary no-op behavior is unchanged.

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

Use shell-native bindings and continuations for the selected parser.
Never use undeclared Python names or one-shot `assert` preconditions.

Use one explicitly labelled fence and valid syntax for the selected parser.
Never emit an unlabelled fence or hardcode syntax for another parser. With
startup files disabled where supported, compile the complete block and validate
the specification without executing it. Then run only
`plan-exec.py --preflight`. Preflight validates identities, history,
pending artifacts and required executable availability; it does not
run import-resolution probes, project checks, staging, an editor or
a commit, access the network or enter normal execution.

First generate `--overview` with the same `--spec` and `--sha256`.
Transfer its stdout verbatim as normal Markdown before the shell
fence. It owns shared conditions, execution context, symbolic runtime
path and diagnostic limits, evidence location and numbered subjects
mapped to `--execute N`. Do not reconstruct these from source or
duplicate boundary subjects in shell comments. This read-only mode
authenticates the spec and identity without running probes or checks.

For Xonsh, generate the entire fence body with the deployed executor:
`python3 <executor> --spec <spec> --sha256 <digest> --render xonsh`.
Substitute shell-quoted absolute executor/spec paths and the pinned
digest. Rendering authenticates the specification and validates
identity, but does not perform preflight or execute any operation.
Transfer stdout verbatim into an `xsh` fence. Do not reconstruct
per-boundary comments, argv, invocations or spacing in agent prose.
Bind exactly `PYVM`, `PLAN_SCRIPT`, `PLAN_SPEC`, and `PLAN_SHA256`
as top-level Xonsh Python variables, not exported environment values.
Use mechanically escaped ASCII string literals, including the digest.
Keep each binding on one line; use short multiline executor calls
with `@(PYVM) @(PLAN_SCRIPT)` and the bound spec and digest.
Live headers use the bound script's basename, normally `plan-exec.py`.
Do not add unused message or single-use root bindings. Keep diagnostic
argv self-contained, independent of these variables. Comments-only
and show output emit no bindings, setup or executable invocations.
After the initial directory change, the generated block sets
`$XONSH_SUBPROC_CMD_RAISE_ERROR = True` so a failed executor call
stops the pasted block instead of continuing to later boundaries.
This setting intentionally remains enabled in the user's shell;
do not restore it or append a command after the final executor call.
Comments-only output does not emit this Xonsh-specific setting.

For Bash, use `--render bash` and transfer stdout verbatim into a
`bash` fence. This shares the same summaries and execution path,
but uses native quoted bindings, `"$PYVM" "$PLAN_SCRIPT"` calls,
and Bash diagnostic argv. Greedily pack complete quoted argv tokens
to the comment width, breaking only between arguments with a
backslash. Indivisible tokens may exceed this soft width limit;
never split a Bash string or executable word. Controls use ANSI-C
quotes. Setup
sets `set -e` before `cd` so failures stop the generated Bash script.
This is not a guarantee about every interactive or conditional shell
context. The setting is not restored. Its show call explicitly uses
`--show --show-shell bash`; plain `--show` remains Xonsh by default.

For other shells, use the same command with `--render comments`.
This emits only generated comments grouped under
source-qualified `# >> ai.skillz/skills/commit-plan/scripts/plan-exec.py`
headers for `--preflight`, `--show` and `--execute N`.
Keep constructing the directory
change and executor argv using the selected shell's correct syntax,
then copy each complete comment group above its matching invocation.
Do not reconstruct underlying operations or descriptions. Validate
the resulting fence with that shell's parser as before; comments-only
rendering does not restrict which shells can receive a commit plan.
Underlying diagnostic argv in these comments is Xonsh-only, even when
the surrounding executor invocations target another shell. Do not
claim those diagnostic lines are copyable in another parser. `--show`
uses the generated Markdown overview followed by the same compact
operation comments, probe catalog and width-controlled Xonsh argv.
It omits executor invocations and preflight/show instructions, and
does not run checks or probes. Version 1 specifications remain valid.

Never assume the user's shell is already in the repository or worktree being
planned. Before any subprocess, change directory to the exact
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

- one `plan-exec.py --preflight` command naming the specification and digest;
- one `plan-exec.py --show` command which renders every project check,
  `git diff --staged` review and `git commit --edit --file` operation as a
  plain command alongside the pinned patch;
- one `plan-exec.py --execute <ordinal>` command per boundary, naming the same
  specification and digest.

Every Python invocation must have the executor's generated shell
comments immediately above it. Preflight comments describe validation
without execution; show comments describe display only. Each boundary
preview includes its inputs and operations; the generated overview
owns conditional no-op, patch skip, order refusal and fail-fast rules.
Important argv, Git cwd, isolated-check cwd and source probes
come from the same descriptions used by execution and `--show`.
Keep common environment metadata once in the preflight group under
`osenv:` using `|_PWD:`, `|_SHELL:`, `|_VIRTUAL_ENV:` and `|_env:`.
Show differing check environments at their uses with values hidden.
Keep preflight/show summaries short under `ops-summary:`. Use one
`# >> plan-exec.py --execute N` header per boundary.
Group patch/message paths under `inputs:` with `|_patch:` and
`|_message:` tags, then staging/structural operations under
`--- staging/checks ---` immediately followed by `cmds:`.
Separate `--- micro-ci ---` from `--- review/commit ---`,
each with `cmds:`.
Omit Micro-CI entirely when no checks are selected. Show every selected
check, including prior PASS skips with evidence, but omit redundant
`=> RUN pending` and `=> RUN resolution probe` annotations.
Separate subsection chunks with actual empty lines. Within
preflight, use `#` separator lines, never whitespace-only lines.
Describe preflight validation and show display positively; reserve
execution commands for execute headers. Use aligned `|_PATCH>`,
`|_CHECK>`, `|_PROBE>`, `|_REVIEW>`, and `|_COMMIT>` tags.
Pending probes use `|_PROBE> probe-N` without redundant RUN prose.
Skipped probes use `|_SKIP-PROBE=> prior PASS`; skipped checks use
`|_SKIP-CHECK=> prior PASS exit=0: <outcome>`. Always place their
raw command or catalog reference on the next line, even when short.
Retain every Micro CI argv, including skips; do not display source
hashes or trees beside skips. Those remain pinned in the spec.
Catalog repeated probes by raw argv plus environment identity; print
each catalog argv once under `probe-catalog:` using `|_PROBE-N>`
and reference its run/skip semantics at uses.
Unique probes may stay inline. Probes still execute before each pending
check, never once per plan; retained prior PASS probes are skipped.
Keep shared overview prose concise rather than listing every internal
subprocess. Runtime-created paths remain placeholders;
environment values stay hidden. Show accurate PWD and explicitly label
Xonsh diagnostic syntax, including comments-only mode. VIRTUAL_ENV may
disclose only a
safe validated selection from the spec or resolved interpreter;
otherwise use `not selected` or redact uncertain configured values.
Never infer selection from an unrelated inherited environment or run
probes just to render. Escape controls and prefix every
physical comment line with `#` so specification text cannot inject
shell commands. Generated Xonsh invocations inject the assigned Python
variables, not POSIX shell quoting. Diagnostic argv and navigation
keep conservative safe tokens bare and inject escaped Python string
literals for other tokens.
`--comment-width` defaults to 69, with a minimum of 40. It bounds
Xonsh command previews including the comment prefix, not metadata
or actual executor invocations. Keep short commands inline after their
tag; otherwise put the tag on its own line and align comment
continuations with `#   ` and shell-safe wrapping. Xonsh long arguments
and executable paths use adjacent escaped string literals inside `@()` without
truncation, expansion or alteration of raw argv.
Use those same lossless tokens for underlying Xonsh comment commands
before control-safe comment prefixing. Diagnostic check argv is copyable
from the repository root, but uses the current checkout without the
hidden environment overlay, not exact isolated execution. Clearly label
staging and commit placeholders as symbolic runtime paths in one
generated overview, alongside the diagnostic argv context, rather
than repeating caveats for every check.

The executor applies the authenticated patch, then runs staged whitespace,
statistics and path checks before every commit. The specification includes
required lint and targeted tests against each exact boundary tree and the
broadest documented safe regression sequence once against the final boundary
tree when one exists. The executor runs `git diff --staged` immediately before
constructing the only permitted commit form:
`git commit --edit --file <authenticated-message-snapshot>`.

Preview and execution must use the same command descriptions. `--show`
renders the diagnostic argv and describes exact-tree isolation before
anything executes. It may show environment variable names, but must hide
their values and the inherited environment. `--execute` announces each
boundary phase, cwd and command immediately before running it, then reports
`PASS`, `SKIP` or `FAIL exit=<status>`. Preserve captured stdout and stderr on
failure, but escape terminal controls and redact authenticated and inherited
environment values. The human must be able to identify the failing
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
temporary root. The executor removes the root afterward. Retain checks
already passed against unchanged boundary evidence with `prior_pass`.

For each `--execute` call, the canonical executor walks backward from `HEAD`
to the recorded initial parent. Each intervening commit must have exactly one
parent and the corresponding recorded boundary tree. It rejects ambient Git
repository/index redirection and ignores replacement refs. It then:

- exits successfully before staging, checks, review, editor or hooks when that
  boundary is already complete;
- executes only the first pending boundary and refuses a later one;
- accepts either the recorded pre-staging index or exact result tree, applies
  the pinned patch only when needed and verifies the result tree;
- runs structural and isolated project checks fail-fast, then staged review
  and its fixed editor-backed commit as one boundary operation;
- after the editor or hooks return, accepts completion only when the new commit
  has the exact expected parent/tree relationship;
- leaves an editor-aborted boundary pending and safe to execute again;
- refuses extra, merge, reordered or tree-mismatched commits as divergence.

Commit OIDs and message text may differ because the editor may change the
message; parent and complete tree identity define completion. Once all exact
boundaries are committed, every `--execute` line is a successful no-op. This
must remain true after a partial run and when unrelated staged changes are
added after full completion.

Use each archived message path directly as its boundary's role-bound message.
Never use `<commit_latest>` in a multi-commit sequence because later message
generation overwrites it. The executor authenticates the archived message
once and passes an immutable snapshot to `git commit --edit --file`.

After bindings and a blank line, use `cd ROOT  # nav to git wkt`,
then the fail-stop setting with
the inline comment `# Stop on failure`. Emit one
blank line after setup. Follow the preflight header immediately with
`# ops-summary:`; use `#` between its summary, osenv and catalog.
Put each invocation immediately after its final comment, then exactly
one blank line between invocation groups. End at the final command
without an extra trailing blank line before the closing fence.
Comments-only output permits empty lines but no executable invocations.

Keep `git diff --staged` as an intentional human review gate even when the
earlier summary and path checks passed. It may open Git's pager; the human can
press `q` immediately to continue when they do not need to inspect the patch.
The executor skips this pager when the boundary is already complete.

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
   rendered as SKIP prior PASS with their commands and evidence;
- the index matches its initial tree;
- one shell-correct command block covers the complete sequence;
- the Xonsh/Bash block is transferred from its native renderer,
  or another
  shell's validated commands include matching `--render comments`
  groups above every Python invocation without reconstructing previews;
- parser evidence follows the documented hierarchy and conflicts are reported;
- the complete block and specification pass no-startup validation, and
  preflight is read-only and cannot enter normal execution;
- the command block starts in the exact absolute repository/worktree root;
- every boundary binds one archived message and the executor constructs only
  `git commit --edit --file <authenticated-message-snapshot>`;
- the executor runs `git diff --staged` immediately before that commit;
- the complete sequence succeeds after partial or complete execution without
  rerunning completed checks, editors, hooks or commits;
- every Python invocation immediately follows its final comment;
- exactly one blank line separates invocation groups, with no extra
  trailing blank after the final command;
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
