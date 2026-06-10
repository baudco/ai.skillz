# Add terminal-clear-method benchmark script

Self-contained `timeit` harness for comparing terminal
clear methods without `timeit`'s mid-run output
wiping the results.

## High-level changes

- Add `bigB/term_clear_bench.py` — single-file
  benchmark, 11 candidates, prints nothing during
  timing and emits one sorted ns/op table once all
  clears have stopped firing.
- Mirror plan into `plans/claude/term-clear-bench.md`.

## Key design choices

- **No output redirection.** Keep writes going to the
  real tty so the terminal-emulator's escape-parse
  cost is included in the measurement. Redirecting
  to `/dev/null` would make every candidate
  artificially close.
- **Force flush on every candidate.** The original
  snippet `print('\033[...]', end='')` does NOT flush
  on a line-buffered tty (no newline) — it would
  measure buffer fills, not real clears. Each
  candidate uses `flush=True` or an explicit
  `flush()` call so the comparison is fair.
- **Ordering, not capture, fixes the "results get
  wiped" issue.** Collect `(name, ns, iters)` tuples
  in memory during the run, print the table only
  after the loop exits. The screen is in
  "post-last-clear" state — a clean canvas — when
  the table renders, so it persists.
- **`timeit.Timer.autorange()` over a hand-picked
  `number=`.** Hits ≥0.2s per candidate, more stable
  than guessing N for op costs that range from
  ~1μs (`os.write`) to ~5ms (`os.system`).

## Candidate ladder

User's originals (with `flush=True` added):
1. `print('\033[H\033[J', end='', flush=True)`
2. `print('\033c', end='', flush=True)`

Bonus candidates progressively shedding Python
overhead (likely-faster, top of table):
3. `sys.stdout.write` + manual flush
4. `sys.stdout.buffer.write` (bytes, skips encoding)
5. `os.write(1, b'\033[H\033[J')`
6. `os.write` with pre-bound `_FD`/`_B` in setup —
   removes attr lookups from the hot loop
7. `os.write` + `\033c` (apples-to-apples vs #2)
8. `os.write` + `\033[2J` (no home, isolates whether
   cursor-home is free)
9. `os.write` + `\033[H\033[2J\033[3J` (full nuke,
   what `clear(1)` actually emits)

Slow controls (bottom of table):
10. `os.system('clear')` — fork+exec
11. `subprocess.run(['clear'])` — fork+exec

## Verification

```bash
python bigB/term_clear_bench.py
```

Run on a real tty (not piped — piping skips the
emulator parse cost we want to measure). Expected
top of table: `os.write` variants beat the `print()`
variants by 2–5×; `os.system`/`subprocess.run` lose
by ~3 orders of magnitude.

## Followups (if useful)

- `--number N` / `--repeat M` CLI flags to override
  `autorange()` if the auto-pick is too noisy on a
  busy machine.
- A `--quiet` flag that writes clears to `/dev/null`
  so the screen doesn't flash during the run — useful
  for measuring just the Python-side cost in
  isolation from the emulator. Distinct measurement,
  worth keeping as an option rather than the default.
