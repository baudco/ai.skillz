# OpenCode Performance Reference

Use this reference with `../SKILL.md`. Commands and paths reflect Linux and
OpenCode 1.18.x; confirm current CLI help and configuration schema before
changing anything.

## OpenCode Checklist

Record the version and invocation:

```text
opencode --version
opencode --help
ps -eo pid,ppid,etime,pcpu,pmem,rss,nlwp,stat,args
```

Relevant local state commonly lives under:

```text
~/.local/share/opencode/
~/.local/state/opencode/
~/.config/opencode/
```

Inspect sizes and metadata before content. OpenCode session databases and
tool output can contain private prompts, code, credentials, and command
results.

Useful OpenCode-specific discriminators:

- `opencode --pure`: compare without external plugins;
- `--no-replay`: disable mini session history replay on resume and resize;
- `--replay-limit N`: cap visible mini replay;
- `--mini`: use the minimal interactive interface;
- a new session: compare against a long resumed session;
- persisted `animations_enabled`: compare render-loop behavior;
- `Ctrl+P`, then `heap snapshot`: collect the upstream-requested memory
  artifact only with user approval.

Config is loaded at startup. After a config, skill, plugin, or persisted UI
setting change, verify whether OpenCode requires a restart before judging the
experiment.

OpenCode runs subagents in the main process in at least some 1.18.x paths.
The absence of a new OS child does not mean no subagent is active. Attribute
work using session events and thread samples as well as process trees.

## Case Study: Sustained CPU During Subagents

### Incident

- Date: 2026-08-06 through 2026-08-07 UTC.
- Harness: OpenCode 1.18.13 on Linux.
- Latest checked release: 1.18.14; its release notes did not document a fix
  for this CPU behavior.
- Repository: `ai.skillz`, approximately 68 MiB and 4,255 files.
- Active process during the main profile: PID `1916444`, session
  `ses_092a25886ffeT0nrIrdkMEcgJK`.
- Symptom: OpenCode used substantial fractions of several cores during
  subagent activity and remained unusually expensive while waiting.

The process typically held 44-47 threads and approximately 0.9-1.15 GiB RSS.
A fresh `opencode debug wait --pure` comparator stabilized near 324 MiB RSS,
showing that the long-running interactive state had a large memory premium.

### Session And Storage Scale

The resumed session covered roughly three weeks and had:

- 835 messages totaling 873,110 bytes;
- 4,729 parts totaling about 10.2 MiB;
- 17,965 events totaling 32,179,450 bytes;
- 8,217,121 cumulative input tokens;
- 129,021,440 cache-read tokens;
- 20 subagent sessions.

The global OpenCode SQLite database was approximately 2.5 GiB with:

- 434 sessions;
- 38,877 messages;
- 221,372 parts;
- 592,872 events.

These measurements established scale but did not prove database I/O was the
hot path. The repository itself was small, and the active process had only
101 inotify watches across three descriptors, so workspace scanning and
watcher overload were not supported as primary causes.

Effective config already had `snapshot: false`; snapshot creation was also
ruled out.

### Thread Attribution

During a controlled subagent run with animations enabled, the hot work was in
the existing OpenCode process rather than a spawned OS child. Samples showed:

- a hot main JavaScript/runtime thread;
- one active generic `Worker` thread;
- seven simultaneously active JavaScriptCore `HeapHelper` threads;
- repeated RSS growth and collection sawtooths, approximately 918-972 MiB in
  one controlled interval.

The combination indicated allocation pressure caused by repeated application
work. The GC helpers were amplifying visible core usage, not independently
identifying the source of allocations.

No Git subprocess loop, child-process storm, or large watcher set appeared.
`fff-bg-*`, notification, Bun pool, and most network threads remained asleep
during representative samples.

### Exact Upstream Match

Upstream issue:

<https://github.com/anomalyco/opencode/issues/34226>

The report exactly matched OpenCode 1.18.13 and described spinner animation
requesting a full TUI render every 40 ms. Those renders create enough
allocation pressure to wake seven `HeapHelper` threads. The reporter measured
a reduction from 28.9% CPU to 1.4% after disabling animations.

The local persisted state initially contained:

```text
"animations_enabled": true
```

The user changed it through OpenCode's UI to `false`; the state was persisted
under `~/.local/state/opencode/kv.json`.

### Animation A/B Result

With animations enabled, subagent waiting produced sustained main-thread,
worker, and parallel GC activity over repeated samples.

With animations disabled:

- the sustained spinner-era allocation/GC churn disappeared;
- receiving and rendering the subagent result still produced a short burst;
- the result-ingestion burst lasted roughly two to three seconds and could
  exceed one core in aggregate across the main, worker, JIT, and GC threads;
- subsequent thread samples declined from an initial GC wave to low
  single-digit activity;
- an eight-second cross-process comparison showed the active session around
  6-8% CPU while its tool was pending, while three other idle OpenCode
  sessions were generally around 1-3% each.

The conclusion was therefore two-part:

1. The animation-driven full-render loop caused the sustained high CPU.
2. Large-result ingestion into a large resumed session still caused brief,
   expected allocation, highlighting, rendering, storage, JIT, and GC work.

Disabling animations was a successful mitigation for the sustained symptom,
not a complete elimination of all transient CPU spikes.

### Memory Interpretation

The active session remained close to 1 GiB RSS after the animation fix. RSS
rose and fell with JavaScriptCore GC, but its post-GC floor remained much
higher than the fresh pure comparator.

Session age and retained history are plausible contributors to that floor,
but this investigation did not collect a heap snapshot, so the retained
object classes remain unproven. Do not label this a memory leak solely from
the RSS difference.

### Tooling Limits

The environment did not have `perf`, `pidstat`, `bpftrace`, `inotifywatch`, or
the `sqlite3` CLI. Database metadata was inspected through available runtime
facilities instead.

Attaching `strace` failed with:

```text
ptrace(PTRACE_SEIZE, 1916444): Operation not permitted
```

Linux reported `kernel.yama.ptrace_scope = 1`. The investigation did not
weaken that security setting and continued with `top -H`, `ps -L`, `/proc`,
controlled comparisons, and upstream source/issue correlation.

Sampling from inside the active agent turn also kept the OpenCode UI busy.
Cross-session idle comparisons were used to reduce, but not eliminate, this
self-observation bias.

### Mitigation Order

1. Keep animations disabled.
2. Start a fresh session instead of repeatedly resuming the multi-week
   supervisor session.
3. Close unused OpenCode instances when no longer needed; four measured
   instances consumed roughly 3.75 GiB RSS combined.
4. For mini-mode resumes, test `--no-replay` or a bounded
   `--replay-limit`, preserving the same workload for comparison.
5. Limit very large retained tool results and compact long sessions when the
   workflow permits it.
6. Upgrade for general fixes, but do not claim a CPU fix without release-note
   evidence and a post-upgrade A/B sample.
7. If RSS again reaches roughly 1-2 GiB and remains problematic, capture an
   OpenCode heap snapshot with user approval and attach it to an upstream
   report.

### Follow-Up Experiments

If the symptom returns:

1. Confirm `animations_enabled` remains false after restart.
2. Sample the same controlled subagent action in the old session and a fresh
   session with identical model, prompt size, and output size.
3. Use an external terminal or delayed sampler to measure true idle after the
   agent turn ends.
4. Record peak CPU, duration, RSS before/peak/after, and active thread names.
5. Compare mini-mode replay defaults against `--no-replay` and one fixed
   `--replay-limit`.
6. Capture a heap snapshot if the high post-GC floor reproduces.
7. Recheck issue `#34226` and current release notes for a merged render-loop
   fix before opening a duplicate.

### Related Upstream Reports

- <https://github.com/anomalyco/opencode/issues/20695>: upstream heap-snapshot
  collection instructions.
- <https://github.com/anomalyco/opencode/issues/39342>: streaming and syntax
  highlighting worker saturation; potentially relevant to result ingestion,
  but not proven here.
- <https://github.com/anomalyco/opencode/issues/32511>: FFF full-home scanning;
  local file and watcher measurements did not support it in this incident.
- <https://github.com/anomalyco/opencode/issues/34867>: MCP tool-list
  notification loops; no matching loop was observed.

### Evidence Retention Note

Raw `top` samples were stored at the time under OpenCode's local tool-output
directory. Those paths are runtime artifacts and may be cleaned, so this
case-study summary preserves the durable findings and approximate ranges.
Future investigations should export sanitized raw samples only when the user
requests a durable report.
