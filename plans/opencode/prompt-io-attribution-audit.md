# Prompt-IO attribution audit

## Handoff

This plan prepares a cross-repository audit of historical Prompt-IO
records whose `## Human edits` sections may understate iterative human
review.

The planning worktree is:

- path: `/home/goodboy/repos/ai.skillz/wkts/prompt_io_attribution_audit`
- branch: `wkt/prompt_io_attribution_audit`
- base: `829af16` (`Count human review as Prompt-IO edits`)
- source repo: `/home/goodboy/repos/ai.skillz`

Another provider should enter through the `open-wkt` lifecycle and
take over the existing owner record explicitly. Do not create a second
worktree for the central audit tooling or plan.

## Objective

Re-evaluate every canonical Prompt-IO main entry against recoverable
human/agent interaction evidence. Correct entries which falsely say
that no human edits occurred, verify accurate entries, and identify
entries whose evidence cannot be recovered without inventing an
attribution history.

The audit must recognize that human contribution includes:

- direct source edits
- review corrections and rejected approaches
- requested deletions or rewrites
- architecture, scope, and compatibility decisions
- acceptance criteria which materially shape the final patch

An agent applying the resulting source lines does not erase the human
contribution.

## Non-goals

- Do not rewrite `.raw.md` records; they remain the captured model
  output.
- Do not infer human contribution from a final diff alone.
- Do not treat every historical `None` claim as automatically false.
- Do not modify disposable worktree copies of logs.
- Do not edit multiple repositories from this central worktree.
- Do not rewrite commit history, session databases, or transcript
  archives.

## Baseline inventory

The initial canonical scan considers only top-level repositories under
`/home/goodboy/repos/*/ai/prompt-io/`. It excludes `wkts/`, legacy
provider worktrees, and `.raw.md` files so checked-out duplicates are
not counted.

| repository | main entries | lexical candidates |
| --- | ---: | ---: |
| `ai.skillz` | 17 | 8 |
| `dotrc` | 11 | 11 |
| `fapnav.nvim` | 2 | 1 |
| `modden` | 135 | 89 |
| `piker` | 32 | 31 |
| `taken` | 4 | 3 |
| `tractor` | 22 | 12 |
| `trowsers` | 11 | 9 |
| `xontrib-watch` | 1 | 1 |
| **total** | **235** | **165** |

“Lexical candidate” is only a priority hint. The current scan matches
phrases such as `None`, `committed as generated`, and `pending user
review`; it does not establish that an entry is inaccurate.

The implementation must regenerate this inventory rather than treating
the table as a permanent source of truth.

## Evidence sources

Use evidence in this order, recording exactly which sources support
each classification.

### Prompt-IO record

Read the main entry and corresponding raw entry first. Extract service,
session, timestamp, git ref, prompt summary, files changed, and the
existing human-edit claim. A raw entry describes generated output but
normally does not prove that no later human review occurred.

### Provider transcript

For Claude Code, resolve UUID-bearing entries beneath:

`/home/goodboy/.claude/projects/<repo-slug>/<session-uuid>.jsonl`

Repository slugs encode the working directory. Some historical entries
use placeholders such as `claude-code-cli`; correlate those by repo,
timestamp, prompt text, and git ref, and mark ambiguous matches as
unverifiable.

For OpenCode, query the database read-only:

`/home/goodboy/.local/share/opencode/opencode-stable.db`

Use Python's standard `sqlite3` module with a `file:...?mode=ro` URI;
the standalone `sqlite3` executable is not installed. Relevant tables
currently include `session`, `session_input`, `session_message`,
`message`, `part`, and `project`. Prefer exact `ses_*` IDs. Entries
using placeholders such as `current` require repo/timestamp/ref
correlation and may remain unverifiable.

Never write to the provider database or transcript tree.

### Git evidence

Resolve `git_ref` in the canonical repository and inspect the linked
commit, surrounding history, and later fix/review commits. Git evidence
can corroborate transcript findings but should not be used to invent a
human review that is absent from the interaction record.

### Related records

Group entries by provider session before review. One long interaction
often produced several Prompt-IO records across repositories, and the
later human turns may explain revisions to earlier generated output.
Reviewing by session avoids repeatedly reading the same transcript and
captures cross-repository human direction.

## Audit classifications

Every canonical main entry receives exactly one classification in the
central ledger:

- `verified-accurate`: the existing human contribution account matches
  the recoverable interaction.
- `correction-required`: evidence shows material human direction which
  the current entry omits or understates.
- `unverifiable`: required session evidence is missing, ambiguous, or
  no longer recoverable.
- `malformed`: the entry cannot be evaluated because required metadata
  or its paired raw record is structurally broken.

These are evidence classifications, not user-owned task completion
states.

## Work package 1: reproducible inventory

Add a read-only audit helper under
`skills/prompt-io/scripts/audit-attribution.py` with commands that:

1. discover canonical top-level repositories without descending into
   worktrees;
2. inventory main/raw record pairs and required frontmatter;
3. flag lexical candidates without classifying them as wrong;
4. group records by provider and session identifier;
5. emit a deterministic JSONL ledger and Markdown summary;
6. never modify Prompt-IO records in scan mode.

Store generated central audit artifacts under a dated directory such
as `ai/prompt-io/audits/20260818/`. Include the scan command, repository
roots, tool version/commit, and content digests needed to reproduce the
inventory.

The helper should accept explicit repository roots so a future audit is
not tied to `/home/goodboy/repos`.

## Work package 2: evidence resolver

Extend the helper, or add a tightly scoped companion, to collect
evidence without making attribution decisions automatically.

For each session group it should:

1. locate exact Claude JSONL or OpenCode database rows when identifiers
   are trustworthy;
2. correlate placeholder IDs using repo, timestamp, git ref, and prompt
   text while retaining all ambiguous candidates;
3. extract human turns and concise references to relevant agent turns;
4. record git commit existence and related review/fix commits;
5. produce an evidence packet for human or agent review;
6. redact secrets and avoid copying complete private transcripts into
   repositories.

Evidence packets should cite local source identifiers, timestamps, and
message/line IDs rather than embedding entire conversations.

## Work package 3: policy for historical corrections

Extend `skills/prompt-io/SKILL.md` with an explicit retroactive audit
contract before changing historical records.

The contract should require:

- evidence-backed corrections only;
- no changes to raw output files;
- an `## Attribution audit` section in corrected main entries stating
  audit date, prior claim, corrected account, and evidence references;
- updating `## Human edits` so normal readers no longer encounter a
  known-false claim;
- leaving unverifiable entries unchanged while listing them in the
  central ledger;
- preserving corrections in ordinary follow-up commits rather than
  rewriting history;
- per-repository Prompt-IO provenance for the audit work without
  recursively generating one log per corrected record.

Decide and document whether an audit batch uses one provenance entry per
repository/session batch or per correction commit. Prefer the smallest
number that still lets each correction be traced to its evidence.

## Work package 4: pilot audit

Run a pilot against `ai.skillz` and `tractor` before scaling to all
repositories. These repositories have known session archives and the
triggering attribution correction.

Prioritize exact-session lexical candidates first, then review the
remaining entries in those repos. Produce:

- the central ledger classifications;
- evidence packets;
- proposed in-place main-entry corrections;
- one isolated worktree and commit plan per affected repository;
- a report of entries which remain unverifiable.

Do not commit corrections automatically. The human reviews every
repository's correction diff and commit message.

Use pilot findings to refine matching confidence, correction wording,
and batching before auditing high-volume repositories.

## Work package 5: full repository audit

Audit remaining repositories in session-grouped order. `modden` is the
largest set and should follow the pilot rather than lead it.

Recommended order:

1. `dotrc`, `fapnav.nvim`, `taken`, `trowsers`, `xontrib-watch`
2. `piker`
3. `modden`

For each repository:

1. verify the canonical checkout and current branch relationship;
2. open a dedicated audit worktree from the intended base;
3. apply only evidence-backed main-entry corrections;
4. add one audit provenance record for the repository batch;
5. run Markdown/frontmatter validation and repository-specific checks;
6. generate a commit plan with every correction visible at the final
   staged-diff gate;
7. leave unverifiable records untouched and carry them in the ledger.

Do not modify unrelated dirty files in canonical checkouts.

## Verification

The central tooling and policy change must pass:

- `bash scripts/validate-skills.sh`
- `py313/bin/python -m unittest discover -s tests -p 'test_*.py'`
- dedicated unit tests for canonical-root discovery, raw/main pairing,
  duplicate-worktree exclusion, frontmatter parsing, lexical candidate
  detection, exact/placeholder session matching, and deterministic
  ledger output

Each repository correction batch must additionally prove:

- only main records classified `correction-required` changed;
- no `.raw.md` file changed;
- every correction cites recoverable evidence;
- every canonical entry appears exactly once in the ledger;
- the sum of classification counts equals the inventory total;
- unverifiable entries retain their original content;
- repository-specific checks pass or their unrelated failure is
  documented.

## Completion report

When execution is complete, write
`plans/opencode/prompt-io-attribution-audit.summary.md` following
`plan-io` conventions. Include final repository and classification
counts, corrected entry paths, unverifiable entries, commits created,
checks run, and deferred evidence gaps.

Do not mark user-owned task files or checklists complete as part of the
report.

## Resume sequence

The next provider should:

1. re-enter this worktree through `open-wkt` with explicit takeover;
2. read this plan and commit `829af16`;
3. regenerate the canonical inventory to detect drift;
4. inspect existing parser/test conventions in `ai.skillz`;
5. implement work package 1 with tests before resolving any private
   transcript evidence;
6. stop for human review after the `ai.skillz`/`tractor` pilot rather
   than silently scaling corrections to every repository.
