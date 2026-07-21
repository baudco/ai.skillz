# Test Harness Reference: tractor

This is an example repository-local `test-harness-reference.md` for
`tractor`. The canonical `/run-tests` skill owns the generic execution,
worktree, failure-inspection, and cleanup workflow.

## Project And Environment

- Project/import: `tractor`
- Test root: `tests/`
- Supported Python: `>=3.13,<3.15`
- Preferred uv environment: `py313`
- Verify `tractor.__file__` resolves inside the active checkout/worktree.
- If no environment is active, ask before running
  `UV_PROJECT_ENVIRONMENT=py313 uv sync --dev`.

Use bare `python` in an active worktree-local environment. Otherwise prefix
commands with `UV_PROJECT_ENVIRONMENT=py313 uv run`.

## Commands

Base command:

```text
python -m pytest
```

Fallback base command:

```text
UV_PROJECT_ENVIRONMENT=py313 uv run pytest
```

Import check:

```text
python -c 'import pathlib, tractor; print(pathlib.Path(tractor.__file__).resolve())'
```

Collection check after module moves:

```text
python -m pytest tests/ -x -q --collect-only
```

Default first-pass flags are `-x --tb=short --no-header` unless the user
requests otherwise.

## Scope And Flags

Resolve bare test files and directories beneath `tests/`.

| Flag | Purpose |
|---|---|
| `--ll <level>` | Tractor log level |
| `--tpdb` / `--debug-mode` | Multiprocess debugger |
| `--enable-stackscope` | Rich task stack inspection |
| `--tpt-proto tcp|uds` | IPC transport |
| `--spawn-backend <name>` | Actor spawn backend |
| `-s` | No capture; required for interactive debugging |

CI covers TCP and UDS separately across Linux and macOS. Run only the
transport requested during targeted iteration; use the matrix when transport
behavior changed.

## Test Layout

```text
tests/
  devx/                  debugger and tooling
  discovery/             registry and discovery
    test_multi_program.py  multiprocess discovery trees
  ipc/                   channel and transport behavior
  msg/                   message codecs and validation
  test_local.py          local actor and registry basics
  test_rpc.py            RPC errors and relays
  test_spawning.py       subprocess spawning
  test_cancellation.py   cancellation semantics
```

## Change-To-Test Mapping

| Changed area | Run first |
|---|---|
| `runtime/` | `test_local.py`, `test_rpc.py`, `test_spawning.py` |
| `discovery/` | `tests/discovery/`, `test_multi_program.py` |
| `_context.py`, `_streaming.py` | `test_context_stream_semantics.py`, `test_advanced_streaming.py` |
| `ipc/` | `tests/ipc/`, `test_2way.py` |
| `spawn/` | `test_spawning.py`, `discovery/test_multi_program.py` |
| `devx/debug/` | `tests/devx/test_debugger.py` |
| `to_asyncio.py` | `test_infected_asyncio.py`, `test_root_infect_asyncio.py` |
| `msg/` | `tests/msg/` |
| `_exceptions.py` | `test_remote_exc_relay.py`, `test_inter_peer_cancellation.py` |

## Quick Checks

```text
python -c 'import tractor'
python -m pytest tests/test_local.py tests/test_rpc.py tests/test_spawning.py tests/discovery/test_registrar.py -x --tb=short --no-header
python -m pytest --lf -x --tb=short --no-header
```

## Known Outcomes

Treat timing or pexpect failures as pre-existing only when both the exact node
ID and historical signature match. In particular, do not classify every
`TooSlowError` as flaky; many Tractor tests intentionally use deadlines as
regression assertions.

Debugger tests need a TTY-compatible no-capture mode and can be more timing
sensitive than the core suite. Docs examples and optional spawn backends may
have platform-specific marks; inspect current marks before classifying them.

## Tractor Runtime Notes

The harness loads `tractor._testing.pytest` and normally allocates
session-unique TCP/UDS registry addresses. Do not require `:1616` to be free
unless a selected test explicitly uses the default registry.

The pytest plugin performs session-end descendant and UDS cleanup. If pytest
dies before teardown, inspect with:

```text
scripts/tractor-reap -n
scripts/tractor-reap --shm --uds -n
```

Ask before running mutating reaper commands. They use SIGINT before a bounded
SIGKILL escalation. Process matching is repository-scoped, but `--shm` scans
all current-user segments under `/dev/shm` and `--uds` scans recognized
dead-PID sockets in the user-wide Tractor runtime directory. Inspect every
dry-run candidate before authorizing those sweeps.

For a multiprocess hang that disappears with `-s`, compare the active capture
mode and log volume before changing runtime code. Fork-based backends may use
`--capture=sys`; follow current plugin policy rather than applying `-s`
universally.
