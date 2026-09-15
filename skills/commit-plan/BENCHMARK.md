# Benchmark capture reference

For repository-maintained experiments, use the fixed test support in
`tests/benchmark_capture.py`, `tests/benchmark_compile.xsh` and
`tests/benchmark_index.py` from the same frozen source checkout.
The existing unittest layout owns this testing utility; canonical
planner behavior remains in the skill's scripts. This reference is
optional experiment guidance, not a step in normal commit planning.

## Why a fixed helper

The archived `benchmark-finalize-handoff-20260914T210930Z` report and
both worker traces record two outer Python string failures: nested
compile quoting and an escaped newline in index comparison. Neither
failure reached its intended subprocess. Failure-to-retry-end spans
totaled 32.758/33.297 seconds; these include scheduling and successful
work, not pure error cost. Preserve that report and its raw failures.

Use the SAME reviewed helper source and invocation contract in both
variants of the next trial. Freeze/hash these files with the trial
materials, including the imported planner/executor for index queries.
Prevalidate with small fixtures before dispatch. Native multiline
blocks and continuations are allowed in both variants: compile the
complete script, never require one-line shell commands or construct
nested Python `-c` capture/verification strings.

Count helper calls and model/tool rounds in both traces, including
failures and retries. Fewer instrumentation rounds do not establish a
production planner latency improvement. A new paired agent experiment
requires its own review; these fixtures are not a benchmark rerun.

## Interface

From the source checkout, this harmless direct-argv example creates a
fresh archive in an existing approved temporary parent:

```xsh
python3 -B tests/benchmark_capture.py --cwd . --output /tmp/nix-shell.04thtZ/opencode/capture-version-01 -- python3 --version
```

For literal quotes, spaces, newlines, or an environment overlay, write
a JSON request and supply `--request request.json` instead of `--`.
All relative request, output, script and expected-evidence paths are
relative to `--cwd`, even when the caller is elsewhere. Child argv is
passed unchanged with `shell=False`; its relative paths use that cwd.
The environment inherits the parent plus `env` (null removes a key).
No environment values or child output are echoed to the terminal.

```json
{"mode": "capture", "argv": ["python3", "--version"], "env": {}, "timeout": 10}
```

Compile accepts `{"mode":"compile","script":"plan.xsh"}`; optional
`"shell":"bash"` selects Bash syntax checking. Xonsh runs initialized
with `--no-rc` and fixed helper source; Bash uses `-n`. Neither executes
the input. Bash startup environment hooks are removed process-locally.
The copied input and its hash identify exactly what was compiled.

Index accepts `{"mode":"index"}` to emit the planner's existing
snapshot as stdout. Add `"expected":"before/stdout"` to compare, or
point it at a builder `prepared.json` to compare its `initial` field.
The fixed worker imports the adjacent canonical `plan-build.py` and
uses `snapshot`, including HEAD, branch, index bytes/stat and stage
metadata. It removes ambient Git variables and disables system/global
configuration process-locally; the planner disables optional refresh,
hooks and fsmonitor. It neither stages nor restores the real index.

## Artifacts and limits

Each invocation exclusively creates a mode-0700 output directory;
existing directories and final symlinks are refused. Use a fresh name
for every retry. Results are immutable through this helper, not a
filesystem write-protection or concurrent-writer guarantee. The private
archive can contain secrets in argv, overlays or child output.

`stdout` and `stderr` retain native bytes. `result.json` records exact
argv, cwd, requested/effective overlays, helper source hashes, Python
version, raw returncode, wall/monotonic start/end nanoseconds, status
and output hashes. Only concise JSON status reaches the terminal.
Capture preserves nonzero exits; signals map to 128 + signal while
retaining the negative raw returncode. Spawn errors are separately
classified as infrastructure errors (125); timeout returns 124.

Stdin defaults to DEVNULL. Optional positive timeout kills/waits only
the immediate child. Direct file capture avoids inherited-pipe hangs;
descendants are not terminated and can still write inherited files.
Use bounded, authorized commands without background descendants for
final evidence. Arbitrary requested argv intentionally executes; this
utility is not a sandbox or an execution-authorization mechanism.

Run the small regression suite from the source checkout:

```xsh
python3 -B -m unittest discover -s tests -p test_benchmark_capture.py -v
```

It requires Python with Xonsh, Bash and Git. It covers literal argv,
non-UTF8 bytes, cwd/overlay handling, exit/signal/timeout/EOF behavior,
missing tools, exclusive archives, complete compile-only inputs, rc
sentinels and shared read-only index comparison. Full deployment tests
also verify packaging of this canonical reference.
