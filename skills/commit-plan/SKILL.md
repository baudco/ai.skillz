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

Repository experiment maintainers can use the optional
[benchmark capture reference](BENCHMARK.md) for fixed instrumentation.

## Repository configuration and runtime paths

Before accessing project guidance or workflow state, read and apply
[the shared runtime contract](../../docs/runtime-state.md#workflow-integration).
Resolve this link from the canonical `SKILL.md` location after
following its symlink. Reuse the resolved paths across composed skills.

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

Default planning permits a human to rename or switch branches in the
same worktree at the pinned HEAD, or at an exact completed boundary
prefix when resuming. `/commit-plan --strict` instead requires the
recorded branch ref: pass `--strict` to `plan-build.py prepare`.
New specs explicitly persist boolean `strict_branch` (default false).
Existing v1 specs without this field retain strict branch matching;
generate a fresh plan to adopt flexible policy, never edit old pinned
evidence. Executor `--strict` strengthens any invocation and is carried
into rendered commands; it cannot weaken a persisted strict policy.
Repository/worktree identity, parent/tree continuity and index checks
are unchanged. Detached HEAD is refused under both policies.
Branch flexibility is not execution authorization: planning never
commits. `--auto` is not supported; autonomous commits remain forbidden.

## 3. Preserve The Starting Index

Use `scripts/plan-build.py` for the mechanical planning path below.
It imports the adjacent executor rather than duplicating execution.
The agent still chooses boundaries, resolves the check catalog once,
reads every prepared diff and writes project-style messages. Do not
generate run-specific Git/schema assembly helpers for supported cases.

Create an input JSON file under the resolved ignored runtime:

```json
{
  "checks": {
    "targeted": {
      "argv": ["python3", "tests/test_example.py"],
      "required_executables": ["git"],
      "env": {},
      "resolution_argv": ["python3", "-c", "import pathlib; print(pathlib.Path.cwd())"]
    }
  },
  "boundaries": [
    {"paths": ["src/example.py", "tests/test_example.py"], "checks": ["targeted"]}
  ]
}
```

Only `boundaries` and one non-empty `paths` list or supplied `patch`
filename per boundary are required. `checks` is an agent-selected
catalog of existing executor command objects, referenced by ordered
names per boundary; omitted selections mean no checks. The example
commands are illustrative, not a repository test recommendation.
Use the loaded `run-tests` resolution probe for actual Python imports.
Whole-file paths are literal repository-relative files, including
deletions, never directories or pathspec expressions. For overlapping
edits, supply a cached patch relative to that boundary's parent tree;
the helper does not synthesize partial hunks. An explicit patch is
frozen at prepare time; later edits to its original source are ignored.

Each check may declare `required_executables`: a list of distinct,
non-empty process-safe argv0 strings, defaulting to `[]` for old v1
specs. Include evidenced child tools from the `/run-tests` catalog:
for example, `git` for Python tests spawning Git, or `cp` and `sed`
for a shell script invoking those utilities. The selecting agent
declares these dependencies; no arbitrary program is parsed to infer
them. Prepare retains the normalized list in the pinned command.

Preflight resolves declared tools without running probes or checks,
using the check's exact environment overlay and the same executable
rules as its main argv and probe. Absolute tools may live outside the
tree (including ignored environments); relative paths must name
executable boundary-tree files. Bare names require absolute, non-empty
`PATH` entries. The isolated runner repeats prerequisite validation
before each pending probe/check against its boundary repository.
Fully reused prior PASS checks require no tool lookup. Availability
does not prove undeclared dependencies or dynamic child environment
changes. Never rewrite `PATH` automatically to bypass a failure.

Run two helper calls, with diff analysis between them:

```xsh
python3 <source>/skills/commit-plan/scripts/plan-build.py prepare --input <input.json> --output <commit_messages>/<timestamp>_<hash>
# Read every NNN.diff, NNN.stat and NNN.paths in that package.
# Write messages.json as an ordered JSON array of complete messages.
python3 <source>/skills/commit-plan/scripts/plan-build.py finalize --prepared <package>/prepared.json --sha256 <prepare-digest> --messages <messages.json>
```

Each call emits phase timings on stderr and a `{path, sha256}` pin
on stdout. Finalize archives exact message bytes with boundary ordinals,
privately rematerializes boundaries to check drift, then publishes
`final/plan.json` and `final/verification.json` after executor preflight.
It never stages the real index, runs project checks or commits.
Use its final pin directly for overview/render/preflight below;
do not reverse-engineer `validate_spec` for the happy path. Maintain
`commit_latest` separately under the `commit-msg` contract.

For a one-call final handoff, select the shell using section 6 before
finalizing and append `--render xonsh` or `--render bash` to finalize.
Optional `--comment-width N` uses the executor's default 69/minimum 40.
This mode emits one JSON receipt line, a blank line, then the complete
native Markdown overview and fenced command block. Parse only the
first line as JSON; the whole stdout is deliberately not JSON.
The receipt retains the final spec `path`/`sha256` and adds `handoff`
with `shell` and `{path, sha256}` pins for `overview` and `commands`.
These are `final/overview.md` and `final/commands.xsh` or
`final/commands.bash`. They are published without replacement; any
render/publication failure removes the incomplete final package.
The pinned spec is unchanged by rendering, including its branch policy.

Keep stdout in the tool result and transfer the returned overview and
fence verbatim. Do not add a dependent receipt read or separate
overview/render calls solely to recover the final pin or handoff.
The helper reuses its validated spec and existing executor preflight;
it does not run a second preflight for rendering. Maintain
`commit_latest` separately as above. Complete the existing no-startup
compile, preflight and artifact acceptance steps in section 6 using
the returned pins; this option does not replace those checks.
Without `--render`, finalize still emits only its original JSON pin.

Prepare records real index bytes/metadata, creates private indexes,
verifies staging patch replay, and emits parent-relative evidence.
Finalize checks HEAD, branch, index and selected whole-file trees for
drift before publishing. Unrelated staged paths which the first
transition would remove are refused, not silently unstaged. Resolve
such boundaries with the human rather than rewriting their index.
An initially absent index remains absent. Both phases remove private
indexes and incomplete phase outputs on handled failures. Existing
packages are never overwritten; use a fresh output directory after
changing boundaries. Completed artifacts are SHA-256 pinned, not
filesystem write-protected. Quiet-worktree assumptions still apply:
fingerprint checks detect drift but do not lock concurrent writers.

Every planner Git process, including executor preflight, disables
hooks and fsmonitor through process-local configuration. Whole-file
paths with active external clean/process filters are unsupported;
supply an explicit cached patch instead. Conversion is never silently
disabled to manufacture different blobs. Selected ancestor symlinks
and symlinked output directory components are refused. Patch/evidence
capture preserves bytes, including CRLF and non-UTF8 content; JSON
snapshots escape undecodable filesystem bytes without data loss.
Adjacent executor import does not write bytecode into deployed source.

Never rewrite the user's real index, restore stale bytes, use an
interactive patch console, stash, clean or overwrite worktree content.
The helper refuses unmerged entries, records staged paths and
`git ls-files --stage --debug`, and uses full canonical object IDs.
Empty initial indexes are allowed. Do not repeat its Git operations.

The shared `scripts/plan-exec.py` owns staging, structural checks,
isolated project checks, staged review, editor-backed commits and
history classification. Never generate a competing state machine.
Record relative project executables only when they are executable
files in the boundary tree. Resolve ignored repository-local tools,
including virtual environment entry points, to absolute paths.
For Python projects, include the documented import-resolution probe
with every distinct interpreter/environment and require exactly one
reported import path beneath `AI_SKILLZ_BOUNDARY_ROOT`.

Absolute helpers under the live repository are accepted only when
ignored and absent from the recorded boundary trees. Record tracked
executables as relative paths so execution resolves their pinned
boundary-tree copies. The executor revalidates executable locations
in the isolated checkout before running the probe or project check.

## 4. Materialize Every Boundary

Resolve the repository's project-check catalog once per plan, before the
boundary loop. Use the loaded `/run-tests` contract and its repository-local
harness reference as authoritative. Use project or CI documentation only where
that authority is silent. Do not rediscover, merge or broaden commands per
boundary.

Prepare compares each temporary index with that boundary's recorded parent tree
for whitespace checks and evidence. Read every resulting diff before
finalizing its message with `/commit-msg`'s normal analysis. Never
compare a later boundary with live `HEAD` or include earlier changes.
Finalize only after every message is complete; a failed boundary blocks
the whole plan, never a request to rerun `/commit-msg` after committing.

Select targeted checks per boundary and assign the
broadest repository-documented safe regression sequence once to the
final tree. A literal test-root run is allowed only when `/run-tests`
classifies it as safe; preserve authorization-required exclusions.
Do not execute project checks while planning unless the user requests it.
Keep all selected commands under Micro CI, including previous passes.
Without exact reusable evidence, checks remain pending.

An optional `prior_pass` object inside each `project_checks` command
records exactly `tree`, `source`, `outcome`, and integer `exit: 0`.
The tree must equal the boundary tree. The attributable source and
outcome summary must be non-empty, safe, non-secret strings. Embed
evidence only after the exact boundary tree, argv, environment overlay
and resolution probe, including declared prerequisites, in that same
authenticated command object have
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
the selected Python interpreter with `plan-exec.py --preflight`.
Preflight checks identities, history and pending artifacts, and inspects
required executables without running resolution or import probes.
Those run only during `--execute` in the isolated boundary tree.
Preflight must not stage, run project checks, invoke an editor or
commit, access the network or enter normal execution.

Use the optional finalize handoff when already returned; otherwise
first generate `--overview` with the same `--spec` and `--sha256`.
Transfer its stdout verbatim as normal Markdown before the shell
fence. It owns shared conditions, execution context, symbolic runtime
path and diagnostic limits, evidence location and numbered subjects
mapped to `--execute N`. Do not reconstruct these from source or
duplicate boundary subjects in shell comments. This read-only mode
authenticates the spec, identity and history without probes or checks.

For Xonsh, use the returned handoff or generate the entire fence body
with the deployed executor:
`python3 <executor> --spec <spec> --sha256 <digest> --render xonsh`.
Substitute shell-quoted absolute executor/spec paths and the pinned
digest. Rendering authenticates the specification and validates
identity/history, but does not perform preflight or run operations.
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

For Bash, use the returned handoff or `--render bash` and transfer
stdout verbatim into a `bash` fence. This shares the same summaries
and execution path, but uses native quoted bindings,
`"$PYVM" "$PLAN_SCRIPT"` calls,
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
renders the diagnostic argv and describes exact-tree isolation before
anything executes. It may show environment variable names, but must hide
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
temporary root. The executor removes the root afterward. Retain checks
already passed against unchanged boundary evidence with `prior_pass`.

For each `--execute` call, the canonical executor walks backward from `HEAD`
to the recorded initial parent. Each intervening commit must have exactly one
parent and the corresponding recorded boundary tree. It rejects ambient Git
repository/index redirection and ignores replacement refs. It then:

- validates a present Git index through a non-blocking regular-file
  descriptor before reading it and repeats that check under the staging
  and commit locks; an initially absent index stays allowed;
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
earlier summary and path checks passed. The executor displays its sanitized
diff through the configured Git pager on an interactive terminal. Quit the
pager with `q`, then press Enter to confirm before the editor; Ctrl-C or
another answer aborts. `--execute <ordinal> --no-pager` instead prints the
sanitized diff directly and keeps the Enter confirmation. No pager runs when
there is no interactive terminal. Pager selection honors `GIT_PAGER` and
Git's `pager.diff` setting before its generic fallback. The configured
pager, editor-backed
`git commit --edit --file`, and local hooks are user-trusted programs:
their own output is not captured or redacted. Automated-check and Git
diagnostics remain escaped/redacted. A completed boundary skips review.

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
