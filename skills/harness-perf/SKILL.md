---
name: harness-perf
description: >
  Diagnose AI coding harness performance problems such as high CPU, memory
  growth, latency, hangs, hot subagents, render loops, and watcher churn. Use
  when OpenCode, Claude Code, or another agent harness becomes slow or
  resource-heavy, or when comparing performance mitigations.
compatibility: >
  Requires process and repository inspection. Linux /proc and procps tools
  are preferred; macOS ps, top, sample, and vmmap are supported fallbacks.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[harness] [symptom or PID]"
---

# Harness Performance

Investigate performance with measurements, controlled comparisons, and a
clear separation between harness work, model latency, project commands, and
instrumentation overhead.

For OpenCode incidents, read `references/opencode.md` before forming the
experiment. It contains an OpenCode-specific checklist and the detailed
2026-08-06 investigation that motivated this skill.

## 1. Establish The Safety Boundary

Performance diagnosis authorizes inspection, not disruption.

- Do not kill, pause, renice, restart, upgrade, attach a debugger, change
  kernel settings, clear caches, vacuum databases, or edit harness config
  without explicit approval.
- Do not delete sessions, logs, databases, snapshots, or tool output.
- Do not install profilers or dependencies unless the user approves it.
- Treat credentials, prompts, tool output, and session databases as private.
  Report aggregate sizes and counts rather than unrelated content.
- Keep repository changes, task states, staging, and commits outside this
  workflow unless separately requested.

Ask before a controlled experiment if it may spend model tokens, invoke a
remote service, mutate a session, or run project code. Prefer an already
authorized low-cost action when one can reproduce the symptom.

## 2. Define The Symptom And Comparator

Record:

- harness name and exact version;
- operating system, architecture, and available memory;
- symptom: CPU, RSS, latency, input lag, hang, disk I/O, network churn, or a
  combination;
- state: idle, streaming, waiting on a tool, executing a tool, compacting,
  replaying history, or receiving a subagent result;
- duration and whether the problem stops on its own;
- active PID, session identifier when safely available, working directory,
  elapsed process time, and command line;
- a comparator: true idle, a fresh session, another idle harness process, or
  the same action with one setting changed.

Do not interpret cumulative `ps %CPU` as current CPU. It is normally an
average over process lifetime. Use interval samples for current behavior.

## 3. Inventory Before Profiling

Collect a cheap baseline before reproducing anything:

```text
ps -eo pid,ppid,etime,pcpu,pmem,rss,nlwp,stat,args
top -b -d 1 -n 5 -p <pid>
```

On Linux, also inspect `/proc/<pid>/status`, `/proc/<pid>/task`,
`/proc/<pid>/fd`, and the process tree when available. On macOS, use `ps`,
`top -l`, `sample`, and `vmmap` equivalents.

Record, without reading unrelated private content:

- RSS, virtual size, thread count, open descriptors, and child processes;
- harness database, log, cache, snapshot, and tool-output sizes;
- session age, message/event/part counts, and token totals if the harness
  exposes them;
- project file count and size;
- watcher counts and watched roots;
- active plugins, MCP servers, language servers, and background indexers.

A large database is not proof that database activity is hot. A large
workspace is not proof of scanning. Keep scale measurements separate from
runtime attribution.

## 4. Attribute CPU By Thread And Process

During the symptom, take several one-second interval samples:

```text
top -H -b -d 1 -n 8 -p <pid>
ps -L -p <pid> -o pid,tid,psr,pcpu,stat,comm,wchan:32
```

Interpret thread names as clues, not conclusions:

- main/runtime thread: rendering, event dispatch, parsing, serialization;
- `HeapHelper` or GC workers: allocation pressure, not necessarily a GC bug;
- `JITWorker`: compilation caused by newly exercised JavaScript paths;
- generic `Worker`: syntax highlighting, database work, plugins, transforms,
  or other runtime jobs;
- watcher threads: filesystem notification handling;
- HTTP/network threads: provider or MCP traffic;
- child processes: project tools, language servers, MCP servers, or shell
  commands outside the main harness runtime.

In per-thread `top` output, the row bearing the process PID is the main
thread. Do not add a separate process-total row to all thread rows. State the
platform's CPU convention; on Linux procps, 100% is approximately one core.

When `strace`, `perf`, DTrace, or debugger attachment is available, use it
only after non-invasive sampling and only within the user's authorization.
If attachment is denied, preserve the error and continue with `/proc`, thread
sampling, logs, and controlled experiments.

## 5. Control Self-Observation Bias

An agent measuring its own harness creates work: streaming text, rendering a
tool status, ingesting tool output, and adding session history. Label samples
accordingly.

Prefer these comparators:

1. another genuinely idle harness process;
2. an external terminal sampling the active PID;
3. a delayed sampler that starts after the agent turn becomes idle;
4. a long, quiet tool wait that produces no streaming output;
5. repeated measurements with the same instrumentation.

Do not call a harness "idle" merely because the sampled project command is
sleeping. The UI may still render a busy indicator or process streamed model
events.

## 6. Run One-Variable Experiments

Form a specific hypothesis, expected signal, and disconfirming result. Change
one variable at a time and preserve equal sample intervals.

Useful comparisons include:

- animation on versus off;
- old/resumed session versus fresh session;
- history replay versus no replay;
- plugins enabled versus documented pure mode;
- MCP server enabled versus disabled;
- small versus large tool result;
- syntax highlighting enabled versus plain output;
- repository root versus an empty directory;
- one subagent versus none.

Record both peak and duration. A two-second result-ingestion burst has a
different cause and impact from a 30-second render loop at the same peak.
Also record RSS before, peak, after, and whether memory returns after GC.

Never present correlation as causation after only one uncontrolled sample.
A strong attribution normally requires thread evidence plus a repeatable A/B
change or an exact upstream implementation match.

## 7. Classify The Bottleneck

Use the evidence to classify the primary and secondary costs:

- `render-loop`: periodic main-thread work while otherwise waiting;
- `allocation-gc`: repeated RSS sawtooths and parallel GC helpers;
- `result-ingestion`: brief parse/render/store burst when a tool or subagent
  result arrives;
- `history-scale`: fresh sessions are materially cheaper than resumed ones;
- `database-io`: measured database calls or I/O dominate;
- `filesystem-watch`: notification threads or scans correlate with changes;
- `plugin-or-mcp`: pure/disabled comparison removes the symptom;
- `child-process`: resource use belongs to a spawned command;
- `provider-wait`: wall time is remote latency with little local CPU;
- `unknown`: evidence is insufficient or contradictory.

More than one classification may apply. Identify which cost is sustained and
which is transient.

## 8. Correlate With Upstream Evidence

Search using the exact harness version, operating system, symptom, thread
names, and triggering state. Prefer source, issue reports with profiles, and
release notes over generic tuning advice.

For each upstream match, record:

- URL and affected version;
- exact matching observations;
- observations that do not match;
- documented workaround;
- whether the current release includes a fix.

Do not assume upgrading fixes the issue unless release notes, a merged change,
or a post-upgrade measurement supports that claim.

## 9. Report And Preserve Follow-Up

Report in this order:

1. symptom and impact;
2. primary diagnosis with confidence;
3. measured evidence and comparator;
4. transient secondary costs;
5. mitigations ordered by risk and expected benefit;
6. unavailable tools and residual uncertainty;
7. exact next experiment if the issue recurs.

When the user requests a durable investigation record, write it beneath
`.ai/harness-perf/` using `YYYY-MM-DD-<harness>.md`. Do not include secrets,
full prompts, or unrelated session content. Writing a report does not
authorize changing issue, plan, or checklist states.

Prefer reversible mitigations first: disable an expensive visual feature,
reduce replay, start a fresh session, cap retained output, or disable a
confirmed plugin. Restart, upgrade, heap snapshots, database maintenance, and
kernel changes require explicit user control.
