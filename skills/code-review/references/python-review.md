# Python Review Evidence

Use this reference to choose evidence sources after the review scope is known.
The repository's own configuration and trusted commands always take priority.

## Analyzer Selection

| Evidence source | Use when | Safety boundary |
|---|---|---|
| Ruff | The repository configures Ruff or uses it in CI | Run check-only with `--no-cache` and JSON output; never use `--fix` |
| Pyright | Pyright is the configured type checker | Use the repository command and machine-readable output when supported |
| mypy | mypy is the configured type checker | Use `--no-incremental`; inspect configured plugins before execution |
| Bandit | Security review is relevant and Bandit is configured | Use JSON output on changed Python paths; deduplicate Ruff security rules |
| Semgrep | A local, reviewed ruleset is configured | Disable metrics; never fetch registry rules implicitly |
| pip-audit | Dependency manifests changed and network use is authorized | Do not install it or query indexes without separate authorization |
| CodeQL/SARIF | Existing local or CI artifacts are available | Consume existing results; do not create a database or upload results implicitly |
| pytest | Runtime confirmation is requested | Delegate to `/run-tests`; do not construct an independent environment |

Any configured command may load repository code, plugins, hooks, or arbitrary
configuration. Static inspection remains the fallback when command execution
has not been authorized or its trust boundary is unclear.

## Repository-Local `py-codestyle`

Before writing Python replacement snippets, suggested patches, or submitted
change examples, inspect the target repository for `py-codestyle/SKILL.md` in
its provider skill trees and any skill roots declared by target configuration.
Common project locations include:

```text
.claude/skills/py-codestyle/SKILL.md
.opencode/skills/py-codestyle/SKILL.md
.agents/skills/py-codestyle/SKILL.md
.gemini/skills/py-codestyle/SKILL.md
.github/skills/py-codestyle/SKILL.md
skills/py-codestyle/SKILL.md
```

A candidate is trusted only when one of these conditions holds before its
contents are opened:

- its resolved `SKILL.md` remains physically within the target checkout;
- it resolves beneath a checked-out `.ai/ai.skillz` path that Git records as
  a submodule in the target repository;
- its exact resolved path matches the canonical `py-codestyle` skill already
  loaded by the harness from a user-approved source; or
- the user explicitly authorizes reading that exact resolved external path.

An ignored local `.ai/ai.skillz` symlink or direct absolute provider link is
not self-authenticating. It needs the loaded-canonical-path match or explicit
authorization above. Do not inspect an external `deploy-manifest.conf` to let
an external tree attest to its own trust. Do not read or follow an arbitrary
external configured root, directory link, or nested `SKILL.md` link; report
it as unavailable and ask before inspecting it.

A trusted symlink at one of those target-local paths counts as the
repository's selection. Resolve it and read the canonical content. A globally
installed `py-codestyle` does not apply merely because the reviewing harness
can discover it; the target repository must deploy or declare it. This target
selection rule supersedes `py-codestyle`'s global auto-application wording for
Python code authored in a review response.

When reviewing a remote tree without a local checkout, inspect equivalent
paths only through repository content already available to the review
provider. Do not fetch, clone, or use a forge API solely for style discovery
without separate network authorization.

If multiple target-local copies resolve to different content, report the
ambiguity and ask which one governs examples. Do not merge competing style
rules. When no target-local skill is available, infer formatting from the
target's instructions, formatter configuration, and nearby Python code.

Apply the selected rules to code authored in the review response, including
fenced examples and suggested diffs. Preserve quotations and evidence from
the existing patch exactly; do not silently restyle reviewed code. A style
rule never changes the finding's severity or excuses an incorrect fix.

## Python-Specific Review Passes

### Behavior And Types

- Trace values across public functions, callbacks, task boundaries, IPC,
  serialization, database rows, and configuration parsing.
- Distinguish a static annotation mismatch from a runtime shape mismatch.
- Check `None`, sentinel, empty-container, and exception paths independently.
- Verify overloads, protocols, re-exports, and package public APIs agree with
  the implementation.

### Async And Concurrency

- Check cancellation propagation, shielded regions, task ownership, nursery
  or task-group lifetime, cleanup ordering, and exception aggregation.
- Look for races hidden by polling, sleeps, broad exception handling, or
  state publication before initialization is complete.
- Verify locks and events protect the same state named by the surrounding
  contract, not merely nearby code.

### Resources And Errors

- Follow files, sockets, processes, transactions, iterators, async generators,
  and temporary resources through success, failure, timeout, and cancellation.
- Check whether retries duplicate side effects or erase the original failure.
- Flag broad catches only when they suppress, misclassify, or leak a concrete
  failure.

### Security And Dependencies

- Review subprocess construction, shell use, path traversal, archive
  extraction, deserialization, dynamic import/evaluation, SQL construction,
  authorization, and secret handling.
- For dependency changes, inspect the lock diff and compatibility impact.
  Advisory lookup is a network action and requires authorization.
- Treat generated analyzer findings as leads. Confirm source, reachability,
  impact, and whether the changed lines introduce or expose the issue.

### Tests

- Identify changed behavior for which the patch supplies no credible evidence.
- Determine whether existing tests reach the boundary where behavior changed,
  without independently prescribing a replacement test.
- Treat a specific bug fix without before/after regression evidence as a
  potential proof gap.
- Delegate failure models, layer choice, deterministic construction, mock
  justification, and authored coverage to `/test-design`.
- Delegate every test command and runtime diagnosis to `/run-tests`.

## Changed-Line Filtering

Changed-line filtering controls review scope, not truth. Prefer findings on
added or modified lines. Keep an off-hunk finding only when the patch changes
control flow, inputs, lifetime, or reachability such that the existing line is
now defective. Explain this relationship explicitly.

Do not hide a high-severity security or data-loss defect solely because its
final sink lies outside the changed hunk.
