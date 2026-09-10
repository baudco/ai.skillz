# Deploying `/commit-plan`

`commit-plan` is a provider-neutral hybrid skill which composes with the
hybrid `commit-msg` and `run-tests` skills. Its `scripts/plan-exec.py` asset
executes pinned boundary specifications without duplicating commits after a
partial or complete run. The skill writes generated messages, specifications
and cached staging patches through `commit-msg`'s ignored repository-local
runtime directories and uses `run-tests` for project-check selection.

## Deployment

Deploy the dependencies first:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-plan <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Use the normal `init` command first for a local symlink or portable submodule
anchor. `commit-plan` stops rather than degrading when either dependency is
missing. A repository-local run-tests harness reference is optional; the
canonical `run-tests` fallback remains available when it is absent.

OpenCode skill deployment installs its dependent command shim automatically.
The explicit command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command commit-plan <repo> \
  --provider opencode
```

Invoke `$commit-plan` in Codex, `/commit-plan` in Claude Code, or
`/commit-plan` through the OpenCode command adapter. Codex uses native
skills and needs no command shim. `--harness codex` and
`--harness agents` both deploy to `.agents/skills/`; a single shared
deployment can also serve OpenCode's skill loader.

Keep `commit-plan`, `commit-msg`, and `run-tests` deployed together. A
root `AGENTS.md` supplies repository guidance; it does not install skills.
See [Shared skills across harnesses](../../docs/shared-skills.md) for local validation
and the distinction between discovery, runtime permissions, and
verified workflow execution. Other compatible harnesses use the same
shared skill bodies with their own invocation mechanism.

Plan generation resolves project commands once and materializes boundaries in
private indexes without rewriting the user's index. Targeted checks remain in
their exact-tree execution boundaries, while the broadest documented safe
regression sequence runs once against the final boundary when one exists. A
check successfully pre-executed against unchanged boundary evidence stays
visible under Micro CI as SKIP prior PASS, including argv and outcome.
Source and tree evidence remain in the pinned specification/artifacts.
Its optional authenticated `prior_pass` object binds the exact
tree and the containing command's argv, env and resolution probe; absent
evidence preserves v1 RUN behavior. Malformed evidence fails closed.
Reused checks need no executable preflight, probe or temporary clone.
This is local plan evidence, not a new CI configuration or cache system.

`--overview` generates shared Markdown context and numbered boundary
subjects mapped to `--execute N`. Transfer it verbatim before the
shell fence, never as executable text or duplicate subject comments.
It explains conditions, pinned evidence, symbolic runtime paths and
the limits of diagnostic current-checkout argv with hidden env values.
It authenticates the spec/identity without running checks or probes.

`--render xonsh` generates the complete command block with lossless
Xonsh diagnostic argv in control-safe comments. `--render comments`
and `--show` use the same compact operation comments and Xonsh argv;
show starts with the generated Markdown overview.
Show omits executor calls and preflight/show instructions; it runs no
checks or probes and retains version 1 specification support.
`--render bash` shares those summaries with native Bash bindings,
quoted variable calls, and lossless Bash diagnostic argv. Controls
use ANSI-C quotes. Greedily pack complete quoted argv tokens, breaking
only between arguments with backslashes. Indivisible tokens may
exceed the soft width limit; Bash strings/executable words never split.
Its setup uses `set -e` before `cd` to stop the generated script on
failure, not to promise fail-stop in every interactive/conditional
context. Its show call uses `--show --show-shell bash`; the default
show and comments-only Xonsh behavior is unchanged. Render remains
read-only and does not run preflight, checks, staging or commits.
Diagnostic argv uses the current checkout without hidden
env values, not exact isolated execution. Staging and message snapshot
placeholders are labelled symbolic runtime paths in one legend.
Live `# >>` headers use the bound script's actual basename;
comments-only headers stay source-qualified without undefined vars.
Shared context and legend live outside the shell block; common env
metadata appears once under `osenv:` with `|_PWD:`, `|_SHELL:`,
`|_VIRTUAL_ENV:` and `|_env:`. Differing check overlays stay visible.
Each boundary uses one `# >>` header. `inputs:` and
`--- staging/checks ---` immediately followed by `cmds:`
precede separate `--- micro-ci ---` and `--- review/commit ---` groups,
each with `cmds:`; empty Micro-CI is
omitted. Repeated probe argv plus environment identities share a
catalog, but probes still run before each pending check. References
identify skipped probes. `probe-catalog:` tags are `|_PROBE-N>`;
pending uses are `|_PROBE> probe-N` and `|_CHECK> <command>`.
`|_SKIP-PROBE=> prior PASS` and
`|_SKIP-CHECK=> prior PASS exit=0: <outcome>` always put the command
or catalog reference on the next line, even for short commands.
`--comment-width` defaults to 69 (minimum 40), including comment
prefixes. Xonsh command previews have a hard width limit, using
lossless adjacent string literals for long arguments and executable
paths. Exactly four
top-level Xonsh Python bindings (`PYVM`, `PLAN_SCRIPT`, `PLAN_SPEC`,
`PLAN_SHA256`) use ASCII string literals, including the quoted digest.
They are not exported. Short multiline executor calls inject these
variables; diagnostic argv stays self-contained. Compile the complete
generated block, not individual physical lines. Comments-only and
show output emit no bindings, setup or executable invocations.
After bindings and a blank line, setup uses
`cd ROOT  # nav to git wkt`, then
`$XONSH_SUBPROC_CMD_RAISE_ERROR = True` with the inline comment
`# Stop on failure`, followed by one blank line.
Every actual Python invocation immediately follows its final comment.
One blank line separates invocation groups; the final command has no
extra trailing blank. Preflight starts immediately with `ops-summary:`
and uses `#` between sections. Subsections retain actual empty lines, also
allowed in comments-only output. Width control also applies to show.
Command continuations align with `#   `; probes retain their status.
Portable comments label Xonsh diagnostic syntax and redact uncertain
virtual-environment selections instead of exposing inherited values.

The executor file is non-executable Python source. Every rendered invocation
selects a Python interpreter before the script path; do not run a bare
`plan-exec.py --<mode>` command. The rendered command block pins one
generated JSON specification by SHA-256, runs the executor's read-only
`--preflight` and `--show` modes, then invokes `--execute <ordinal>` for each
boundary. The executor recognizes an exact
completed parent/tree prefix before touching the index, checks, editor or
hooks. Repeating the complete block therefore skips committed boundaries and
resumes the first pending boundary; unexpected history stops as divergence.

`--show` plainly renders each project check, `git diff --staged` review and
`git commit --edit --file` command from the same descriptions execution uses.
At runtime the executor prints each phase, cwd and command before it runs,
reports its outcome and preserves captured automated-command diagnostics.
Environment variable names may be shown, but their authenticated values and
the inherited environment remain hidden. Captured output escapes terminal
controls and redacts environment values. For `--execute`, the staged diff is
sanitized before display. On an interactive terminal, the configured Git
pager opens by default; `q` returns to an Enter-to-continue review prompt.
Selection honors `GIT_PAGER`, `pager.diff`, then Git's generic pager.
`--no-pager` prints the sanitized diff directly instead. No pager runs in
noninteractive mode. The configured pager, editor and user-configured hooks
retain their terminal; their own output is trusted, not redacted by the
executor.

`--preflight` and `--show` do not stage or commit. `--execute <ordinal>`
applies the authenticated staging transition and opens the editor-backed
commit after checks and review. Quit and restart OpenCode after deployment
or update.
