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

- Match changed behavior to existing test boundaries and fixtures.
- Ask whether a test would fail before the patch and pass after it.
- Require regression coverage when the patch fixes or reopens a specific bug,
  especially for concurrency, cancellation, serialization, and cleanup.
- Do not demand broad integration coverage when a focused deterministic test
  proves the relevant invariant.

## Changed-Line Filtering

Changed-line filtering controls review scope, not truth. Prefer findings on
added or modified lines. Keep an off-hunk finding only when the patch changes
control flow, inputs, lifetime, or reachability such that the existing line is
now defective. Explain this relationship explicitly.

Do not hide a high-severity security or data-loss defect solely because its
final sink lies outside the changed hunk.
