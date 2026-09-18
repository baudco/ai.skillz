Summarize commit-plan latency experiments and landing

- Retain native Bash/Xonsh rendering, boundary preparation,
  explicit branch policy, consolidated handoff, child-tool
  prerequisites, and fixed benchmark capture helpers.
- Distinguish fewer planning rounds from proven latency gains.
- Preserve historical and controlled samples, including failures.
- Separate interactive responsiveness from plan-generation latency.

## Findings

Historical simpler workflows do not establish a reliable faster
default. V5's initial advantage does not reproduce consistently in
matched trials. Retain the executable architecture rather than revert
solely on those observations.

Actual exported traces identify OpenCode, openai/gpt-6-astra, medium.
Recorded tool execution occupies roughly 3-5 seconds of runs lasting
several minutes. Remaining wall time mixes generation, scheduling,
network/provider waits, and harness overhead; it is not measured pure
reasoning or proof of a harness bottleneck. Final response generation
after the last tool frequently occupies roughly 35-42 seconds.

Consolidated finalization removes two handoff rounds. A cleaned-up
same-source pair records 316.780 versus 311.680 seconds, insufficient
to establish a general speedup. Fixed capture helpers remove observed
quoting retries and improve measurement reliability.

Explicit batching changes 26 to 20 rounds, then 32 to 22. The first
treatment fails a literal message assertion; the confirmation baseline
fails a 67-column message rule. Neither pair has two fully accepted
plans, so successful-plan latency improvement is unestablished.
Do not promote the experimental instructions as a proven optimization.

## Retained Evidence

Main-checkout runtime archives contain historical screening and
matched V5/current trials, plus the initial finalize-handoff traces.
The linked worktree contains the clean handoff, batching experiment,
and confirmation archives under `.claude/skills/commit-msg/msgs/`.
These machine-local ignored artifacts are not durable published
benchmark evidence; export a reviewed reproducibility bundle before
deleting worktrees or promising public replication. Raw session exports
can contain contextual data and require review before publication.

## Recorded Branch State

Local `main` and recorded `github/main` both point to `649056f`,
including PR #17. `origin/main` is a different older tracking ref;
no fetch or live-forge check was performed in this assessment.

`wkt/finalize_render_handoff` at `63a9175` contains 16 commits above
recorded main. `commit-plan_w_micro_ci` at `e373184` contains the
first 13. Relevant linked worktrees are clean; the main checkout on
`pyskillz` has unrelated and overlapping dirty work to preserve.

The functional planner candidates, in existing dependency order:

| Commit | Subject |
| --- | --- |
| `77bec10` | Harden test orchestration |
| `87516c9` | Make execution idempotent |
| `8ce63d4` | Expose executor commands |
| `fd3ec93` | Render observable micro CI plans |
| `e373184` | Add mechanical planning and strict policy |
| `b14d1c3` | Render the final handoff in one call |
| `57822d3` | Validate declared child executables |
| `63a9175` | Add fixed benchmark capture/compile helpers |

This is not a standalone cherry-pick recipe. Shared deployment/runtime
changes (`6ad7cda`, `e1fe69b`, `3c5afd9`, `3cbcedc`) are interleaved;
the runtime migration changes the executor. Review-workflow commits
(`fb6c53f`, `b502352`, `2403fb6`, `96d6305`) form another interleaved
series. Resolve prerequisites rather than silently landing all 16.

## Landing And Deferred Stack Proposal

Use the existing branch stack; a fresh integration branch is optional,
not required. Verified existing base/head pairs are:

| PR | Head | Base | Unique commits |
| --- | --- | --- | ---: |
| 1 | `wkt/commit_plan_executor` | `main` | 3 |
| 2 | `wkt/codex_shared_skills` | `wkt/commit_plan_executor` | 4 |
| 3 | `wkt/finalize_render_handoff` | `wkt/codex_shared_skills` | 9 |

Shared skills at `3cbcedc` includes executor runtime migration, so
its dependency on executor is substantive. The first two branches
already have clean committed boundaries. The registered sibling
worktree at the shared tip has uncommitted work; do not include it
implicitly. Live forge refs/PRs still require verification before
publishing or retargeting any PR.

PR 3 currently includes four Tuicr commits and five planner commits.
For a narrow planner PR, the prospective selective replay is exactly
`96d6305..63a9175` onto shared tip `3cbcedc`. Preserve the mixed source
history before any rewrite. Deployment tests overlap, so clean replay
and semantic independence must be verified rather than assumed.
An ordinary rebase onto executor would be a no-op: it is already an
ancestor. Dropping the shared commits would remove real prerequisites.
Keep the Tuicr series for separate review instead of silently dropping
its work or bundling it into a latency-labelled PR.

Do not drop `6ad7cda..b14d1c3`: Git's range excludes `6ad7cda`
itself but includes runtime migration, all four Tuicr commits, and
the renderer, builder/strict-policy, and consolidated handoff commits.
Later prerequisite validation and benchmark helpers depend on that
planner foundation. The unwanted contiguous Tuicr segment is
`3cbcedc..96d6305`; the five planner commits after it are what should
be replayed onto `3cbcedc` for a narrow PR 3. Shared skills remains
its own official PR, not part of the planner PR's reviewed diff.

The rebuilt deferred source at `6484933` is the better starting point
than concatenating both deferred histories. Its staging-preservation
contract comes principally from `8fd71ed`, hardened by `6484933`;
`7796acb` covers parser-safe rendering and `5424f11` boundary-owned
review replies. Some earlier commits restore coupling removed by
PR #17. It lacks the modern executable scripts: a clean text replay
alone would not implement its guarantees.

Leave both deferred branches unchanged for much later follow-up.
The human explicitly deferred their additional complexity until its
latency and workflow costs can be justified. No immediate rebase or
implementation of their unrelated-staging contract is planned.

Branch the delegation/multi-harness work from the settled executable
base. Prefer a sibling of unfinished deferred-index work so measurement
does not require landing that larger execution change first.

All implementation commits through `63a9175` are already committed.
These review drafts are untracked and need a separate scoped docs
commit after review. Dirty main-checkout files are not uniformly
duplicates and must not be swept into that commit or discarded.

No cherry-pick, rebase, merge, new branch, commit, or push is performed
by this draft. The human approved the narrow Tuicr separation above,
after reviewing and saving these three drafts in a scoped docs commit.
After landing/settling the executable stack, branch the
delegation and supervisor experiment without depending on deferred
virtual-index work. Review Firstmate before adapter implementation.

## Deferred

- Default delegation and interruption/responsiveness testing, drafted
  in `commit-plan-delegation-draft.md` alongside this summary.
- Trio/Tractor supervision experiment and cross-harness attribution.
- pi capability discovery and provider support.
- Unrelated-staging preservation and recovery semantics.
- Fold-friendly presentation, phase counts, and ai.reply integration.
- Opt-in harness permissions, including child-worker access.
- CI/shell configuration and a reusable skill-benchmark methodology.
- Earlier review-phase SIGPIPE report, still not reproduced/fixed.

## Stats

Recorded finalize stack: 16 commits above local main; eight functional
planner candidates listed above, with shared prerequisites unresolved.
Latest source checkpoint: `63a91759f2cbad64eff178b446d5e6efcf638bfc`.
Most recent implementation verification: 67 planner tests, five capture
tests, 45 deployment cases, Ruff, and skill validation (five warnings).
No fresh implementation tests are run for these review drafts.

(this summary was generated in some part by opencode;
model: gpt-6-astra; provider: openai)
