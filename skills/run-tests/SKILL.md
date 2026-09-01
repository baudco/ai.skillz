---
name: run-tests
description: >
  Run a repository's test suite or targeted subsets using its local test
  harness reference. Use when the user asks to run tests, inspect previous
  failures, verify changes, diagnose hangs, or check for regressions.
compatibility: >
  Requires repository file access and the project's test runner. Optional:
  git, uv, nix, pytest, and tractor runtime diagnostics.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[test-path-or-pattern] [--opts]"
---

# Run Tests

Run the active repository's tests using a shared safety and diagnosis
workflow plus repository-owned harness instructions.

Never assume that a command, package name, test layout, backend, fixture, or
known failure from another repository applies here.

## 1. Establish Repository Context

Use `git rev-parse --show-toplevel` when Git is available. Also inspect
`--git-dir` and `--git-common-dir` to detect a linked worktree.

Always look for the local override at:

```text
<repo-root>/.claude/skills/run-tests/test-harness-reference.md
```

Resolve this path from the active repository root, not relative to this
canonical `SKILL.md`; the base may be symlinked from another checkout.

When the override exists:

- read it before constructing commands;
- treat it as authoritative for environment setup, package/import name,
  test roots, runner commands, default flags, backend matrices, fixture
  invariants, known outcomes, and change-to-test mappings;
- reject it as unfinished if it still contains Jinja markers such as `{{`
  or `}}`, then report the deployment issue.

When the override is absent, inspect `pyproject.toml`, `pytest.ini`,
`tox.ini`, `noxfile.py`, `conftest.py`, test documentation, CI config, and
test directories. Use only commands supported by repository evidence. Tell
the user that no local harness reference was found; do not import another
repository's conventions.

## 2. Parse The Request

Determine:

- scope: full suite, directory, file, node ID, keyword expression, or
  previous failures;
- explicit options and backend/environment selections;
- whether the user wants execution, collection only, failure inspection,
  or hang diagnosis;
- whether recent changes imply a smaller first-pass subset.

Preserve explicit user flags. Do not silently broaden a targeted request or
run every expensive backend when one was named.

Resolve bare test filenames and directories beneath the override's test
root. If more than one path matches, ask before choosing. Never guess an
exact node ID.

## 3. Validate The Environment

Before running tests, record the repository/worktree root, current Python
executable, active virtual environment, and the environment command required
by the override.

For Python projects:

1. Prefer the active project environment when it belongs to this worktree.
2. Otherwise use the override's documented wrapper, such as `uv run` or
   `nix develop ... --command`.
3. Do not run `uv sync`, create an environment, or modify a lock file without
   asking first.
4. Run the documented import check. Confirm the imported package resolves
   inside the active repository/worktree rather than another checkout.
5. Run the documented collection check after module moves or collection
   failures. Collection is optional for a known narrow test unless the
   override requires it.

If no override documents environment setup, infer conservatively from
project files and report the inferred command before running it.

## 4. Build The Test Command

Start with the override's base command and environment wrapper. Add, in
order:

1. the resolved test scope;
2. repository defaults that do not conflict with user flags;
3. explicit user options unchanged.

Prefer a targeted progression:

1. import or collection check when relevant;
2. tests directly mapped to the changed code;
3. related integration/backend coverage;
4. the full suite only when requested or warranted.

Do not invent flags from a shared runtime plugin. A project may rename,
override, or conflict with plugin options; the local reference owns the
actual command surface.

## 5. Check Tractor Runtime Health Conditionally

Apply this section only when the override says the suite uses Tractor, the
test harness loads `tractor._testing.pytest`, or failures clearly involve a
Tractor actor tree.

Modern harnesses may allocate session-unique TCP or UDS registry addresses.
Do not require `127.0.0.1:1616`, assume `/tmp/registry@1616.sock`, or kill a
process merely because it imports Tractor.

Before a run, inspect runtime state only when the override identifies a fixed
registry or previous aborted runs make leaked actors plausible. After a
timeout, cancellation, `Ctrl+C`, or hard crash:

1. inspect listeners, sockets, and process command lines;
2. scope candidates to the active repository, known parent PID, configured
   registry, or harness-specific identifiers;
3. show the candidates and ask before signaling or unlinking anything;
4. prefer SIGINT and a bounded wait;
5. use SIGKILL only for confirmed survivors and only with explicit approval.

Never use a broad `pkill` pattern that can match another repository's live
application or test session.

If `scripts/tractor-reap` exists in this repository, prefer its dry run:

```text
scripts/tractor-reap -n
```

Inspect the output before asking to run the mutating form. Use `--parent`,
`--shm`, or `--uds` only when the local script supports them and the observed
failure calls for that scope. Do not assume downstream repositories contain
the script.

## 6. Execute And Report

Use a timeout suitable for the requested scope and the repository guidance.
Do not hide a long-running suite behind an arbitrary short timeout.

Report:

- the exact command and environment used;
- pass, fail, skip, xfail, and deselection counts when available;
- failed node IDs and a concise traceback/signature;
- whether failures appear code-related, expected, flaky, environmental, or
  still unclassified;
- checks not run and why.

Known failures are evidence, not blanket exemptions. Match the exact node ID
and expected signature from the local reference before classifying a result
as pre-existing.

## 7. Inspect Previous Failures Directly

When asked what failed previously, read pytest's cache without collecting or
running tests:

```text
<repo-root>/.pytest_cache/v/cache/lastfailed
```

Parse the JSON object and keep node IDs beneath the override's configured
test roots. Report stale or external entries separately. Do not use
`--collect-only --lf` merely to inspect the cache; changed parameter IDs can
cause pytest to collect a broader file and obscure what was recorded.

When rerunning, use the repository's documented last-failed command or append
`--lf` only if the runner is pytest-compatible.

## 8. Diagnose Capture-Pipe Hangs

Suspect inherited pytest capture pipes when all of these are plausible:

- a multiprocess or actor test hangs only with capture enabled;
- child processes remain alive while emitting high-volume error logs;
- the exact test completes with `-s` or the harness's no-capture mode;
- the parent is waiting for child exit or capture EOF.

Retry only the exact hanging node with the local no-capture option. Treat the
retry as a diagnosis, not proof that application logic is correct. Compare
the project's configured capture mode first; fork-based backends may require
`--capture=sys` rather than a universal `-s` workaround.

Lower unnecessary debug logging and inspect surviving descendants. A child
that inherits stdout/stderr can keep a capture pipe open or block when its
buffer fills, preventing pytest from observing EOF. Use the conditional
cleanup rules above after diagnosis.

## 9. Preserve Human Control

Running tests does not authorize staging, committing, pushing, changing task
states, or rewriting expected outcomes. Leave fixes unstaged unless the user
explicitly requests staging. Never commit automatically.
