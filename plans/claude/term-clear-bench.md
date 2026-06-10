# Benchmark: fastest way to clear the terminal from Python

## Context

You want to compare `print("\033[H\033[J", end="")` vs `print("\033c", end="")`
under `timeit`, but the screen keeps getting wiped before you can read the
result. The fix is mostly about **ordering and flushing**, not redirection — if
we redirect output to a pipe we stop measuring what actually matters (the
terminal emulator's own escape-parsing cost). So we keep writes going to the
real tty, but arrange the harness so the result print happens *after* the last
clear, on the now-quiet screen.

There's also a measurement bug worth calling out: `print(..., end="")` writes
to a line-buffered stdout with no newline, so it may **not flush** before
`timeit` returns. Your original snippets may be timing buffer fills rather than
real terminal clears. The harness forces `flush=True` (or calls `flush()`
explicitly) on every candidate so the comparison is fair.

## Approach

One self-contained script: **`bigB/term_clear_bench.py`**.

1. Define candidates as `(name, setup, stmt)` triples — see list below.
2. For each, run `timeit.Timer(stmt, setup=setup).autorange()` (auto-picks an
   N that takes ≥0.2s — more stable than a hand-picked `number=`).
3. Collect results into a list **in memory**. Print **nothing** during the run.
4. After the loop completes, no more escape sequences fire. Emit a final
   `\n\n` to nudge the cursor off home in case the last `\033c` reset things
   oddly, then print a sorted ns/op table. The table lands on a clean screen
   and persists.

That's it. No tty redirection, no subprocess gymnastics — just don't print
between clears.

## Candidates

Your originals (with `flush=True` added so we measure actual terminal work):

| # | name | stmt |
|---|------|------|
| 1 | `print + CSI home+ED` | `print("\033[H\033[J", end="", flush=True)` |
| 2 | `print + RIS` | `print("\033c", end="", flush=True)` |

Bonus candidates, progressively shedding Python overhead:

| # | name | stmt | setup |
|---|------|------|-------|
| 3 | `sys.stdout.write + flush` | `_w("\033[H\033[J"); _f()` | `import sys; _w=sys.stdout.write; _f=sys.stdout.flush` |
| 4 | `stdout.buffer.write (bytes)` | `_w(_B); _f()` | `import sys; _w=sys.stdout.buffer.write; _f=sys.stdout.buffer.flush; _B=b"\033[H\033[J"` |
| 5 | `os.write to fd 1` | `_w(1, _B)` | `import os; _w=os.write; _B=b"\033[H\033[J"` |
| 6 | `os.write, pre-bound fd` | `_w(_FD, _B)` | `import os, sys; _w=os.write; _FD=sys.stdout.fileno(); _B=b"\033[H\033[J"` |
| 7 | `os.write + RIS` | `_w(_FD, b"\033c")` | (as #6, different payload) |
| 8 | `os.write + ED only` | `_w(_FD, b"\033[2J")` | clear without homing — see if cursor-home is free |
| 9 | `os.write + full nuke` | `_w(_FD, b"\033[H\033[2J\033[3J")` | home + ED + clear scrollback (matches `clear` on most terms) |

Slow controls so the table has shape:

| # | name | stmt |
|---|------|------|
|10 | `os.system("clear")` | `os.system("clear")` |
|11 | `subprocess.run(["clear"])` | `subprocess.run(["clear"])` |

**Prediction** (so we can sanity-check the output): #6 ≈ #5 ≈ #4 should win,
likely 2–5× faster than #1/#2 (the print path does locale-encoding +
`sys.stdout` lookup + arg parsing per call). #10/#11 will be ~1000× slower
because of fork+exec. `\033c` (RIS) may be slightly slower than `\033[H\033[J`
in some terminal emulators because it triggers a full reset (palette, modes,
scrollback) rather than just a screen wipe.

## Files

- **Create:** `bigB/term_clear_bench.py` — the script above. `bigB/` already
  exists.
- **Copy plan to:** `plans/claude/here-s-a-tricky-one-serialized-turing.md`
  per your `./plans/claude/` convention. (Execution phase only — read-only
  during planning.)

## Verification

```bash
cd /home/goodboy/repos/ai.skillz
python bigB/term_clear_bench.py
```

Expected: screen flashes a few times, then a table like:

```
rank  ns/clear   method
   1     ~3000   os.write, pre-bound fd       (\033[H\033[J)
   2     ~3100   os.write to fd 1
   3     ~3500   stdout.buffer.write (bytes)
   ...
  10    ~5e6     os.system("clear")
```

Re-run once or twice — `autorange()` is stable but terminal-emulator load
can wobble timings by 10–20%. Top-3 ranking should be stable across runs.

If the table doesn't appear at all on the first run: the last benchmark was a
`\033c` (RIS) and your terminal swallowed our trailing newlines. Scroll up or
press Enter. (We can also add an `input("[enter] for results")` gate before
the print if this keeps happening — but I'd rather not, because some terminals
echo that prompt mid-clear and it's ugly.)
