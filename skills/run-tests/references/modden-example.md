# Test Harness Reference: modden

This is an example repository-local `test-harness-reference.md` for
`modden`. Keep `tests/testing.md` as the detailed harness authority.

## Project And Environment

- Project/import: `modden`
- Test root: `tests/`
- Supported Python: `>=3.13`
- Preferred uv environment: `py313`
- Sway environment: `nix develop .#test`
- i3/Xephyr environment: `nix develop .#i3test`
- Verify `modden.__file__` resolves inside the active checkout/worktree.

## Commands

Base command for arbitrary unit tests and node IDs:

```text
UV_PROJECT_ENVIRONMENT=py313 uv run pytest
```

Import and worktree-resolution check:

```text
UV_PROJECT_ENVIRONMENT=py313 uv run python -c 'import pathlib, modden; print(pathlib.Path(modden.__file__).resolve())'
```

Collection check:

```text
UV_PROJECT_ENVIRONMENT=py313 uv run pytest tests/ -q --collect-only
```

Fast deterministic subset:

```text
UV_PROJECT_ENVIRONMENT=py313 uv run pytest tests/test_wks_save_fidelity.py tests/test_twm_config.py tests/test_repr_hardening.py tests/test_spawn_trees_hardening.py tests/test_multiwin_subwin.py -x --tb=short --no-header
```

Headless Sway integration:

```text
nix develop .#test --command uv run pytest tests/ --twm sway --headless -x --tb=short
```

Headless i3 integration:

```text
nix develop .#i3test --command uv run pytest tests/ --twm i3 --headless -x --tb=short
```

Two-backend matrix from the shell containing both stacks:

```text
nix develop .#i3test --command uv run pytest tests/ --headless --twm sway --twm i3
```

## Backend And Flag Semantics

- `--twm` is repeatable and currently accepts only `sway` and `i3`.
- `--headless` uses wlroots headless mode for Sway and an invisible virtual
  display for i3.
- Per-test `virt_disp` markers override the session visibility default.
- `--ll` controls Modden logging.
- `--tl` controls Tractor runtime logging.
- Hyprland and `--sw` are planned, not active harness options.

## Fixture Invariants

Tests select example config beneath `example/modden/`, then copy it into a
function-scoped temporary config directory. Before diagnosing a workspace or
config mismatch:

1. identify the test's `modden_conf` marker;
2. resolve the source fixture inside `example/modden/`;
3. reject any source symlink that escapes the repository, especially one
   targeting `~/.config/modden`;
4. confirm the runtime uses the copied temporary directory;
5. rerun the full relevant file after a last-failed pass to expose ordering
   or environment leakage.

Repository-local fixture symlinks are valid when their resolved targets stay
inside the example tree. Environment variables changed by display/runtime
fixtures must be restored after each scope.

## Change-To-Test Mapping

| Changed area | Run first |
|---|---|
| config/workspace formats | `test_conf_fmts.py`, `test_wks_save_fidelity.py`, `test_basic_wkss.py` |
| i3 config or keyboard input | `test_twm_config.py`, `test_kb_input.py`, `test_wmctl.py` |
| layout geometry/reduction | layout PPT, reduction, root-order, basic workspace tests |
| runtime daemon/environment | `test_daemon.py`, `test_basic_spawning.py` |
| repr/process/save hardening | repr, spawn-tree, and save-fidelity tests |
| i3/Sway window identity | `test_multiwin_subwin.py`, then live `test_wmctl.py` |

Run deterministic unit tests before nested-WM integration tests.

## Known Outcomes

Inspect current marks for exact conditions. Existing parked or backend-
specific outcomes include cases in `test_layouts.py` and
`test_layout_reduce_failure.py`; do not inherit Tractor's known-failure list.

Host capability skips are expected when Sway, a Wayland compositor, Xephyr,
or i3 is unavailable. Use the appropriate Nix shell before treating those
skips as harness regressions.

## Tractor Runtime Notes

The suite loads `tractor._testing.pytest` but uses randomized registry
addresses. Do not require `:1616` to be free. `scripts/tractor-reap` is not a
Modden-local command; inspect and clean only processes tied to the current
test session.

When transport behavior matters, run TCP and UDS in separate pytest sessions
because the Tractor fixture accepts one transport per session.
