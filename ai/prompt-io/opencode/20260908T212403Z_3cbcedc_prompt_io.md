---
model: openai/gpt-6-astra
service: opencode
session: consent-policy-probes-20260908
timestamp: 2026-09-08T21:24:03Z
git_ref: 3cbcedcfdf61f633bc77a3b25b933b7b2b4dfb1d
scope: code
substantive: true
raw_file: 20260908T212403Z_3cbcedc_prompt_io.raw.md
---

## Prompt

The human revised the initial migration policy and explicitly said:
"all sounds good, do the changes and try the migration again and
report back". They required inventory and a loud non-mutating halt
without move-or-preserve consent, an agent-ready prompt, explicit
relocation, truthful preservation reporting, and unchanged canonical
link safeguards. They requested targeted/full tests and independent
historical scenarios without modifying the existing probe or source
index, committing development work, or changing task markers.

The historical base was 7b7ecb67473fe23d2f8d684c1936ffd7b7ca261f;
the success-path base was f148fbcc23ee8bf75bd37152a8b68a763d96d943.
Expected skill contents/adapters came from immutable PR93 commit
45d0f003fc8793fbaffd2506fff652be86508fa7. The unsafe historical
tracked absolute commit-msg link was not removed or untracked.

## Response Summary

Implemented --repo-skills move|preserve. Dry-run is not consent;
unmanaged entries require a decision before migration proceeds.
Explicit preserve leaves local sources untouched and reports them
as not migrated. Explicit move retains tracked clean-tree safeguards.
Updated implementation, deployment docs, and regression fixtures.

This entry supersedes the implicit-relocation policy described by
20260908T161601Z_3cbcedc_prompt_io.md. The original provenance and
archived commit package were preserved rather than rewritten.
That package is stale and must be regenerated before use.

## Human Contributions

The human rejected implicit relocation and supplied the required
consent policy, negative safety case, historical bases, comparison
commit, fixture-preservation requirement, and experiment scope.
These are substantive human-directed design changes applied by the
agent. No acceptance or task completion state is inferred.

## Verification

11 targeted deployment cases and 50 full deployment cases passed,
including 42 embedded Python tests. Skill/deployment validators and
syntax/diff checks passed, with three pre-existing skill-size warnings.
The inherited Python 3.13 executable was used only for stdlib evidence
helpers and repository tests, not Piker application tests or an
environment claimed to belong to the historical worktrees.

Eight detached probes cover absent choice and both explicit choices
at two historical bases, private-index staging, and separately labelled
canonical bootstrap. All default real indexes remained unchanged.
The historical tracked-link refusal was preserved. Successful move
matched ten skill blobs/modes and four adapters to PR93 and repeated
without changes. A missing ignored canonical link explains raw Git
fixture validation failure; the separately bootstrapped fixture passed
whole-deployment validation. No old evidence was deleted.

Detailed local evidence and the retained fixtures are indexed by
/tmp/nix-shell.Vjl4xl/opencode/REPORT.md, with new command, filesystem,
index, mode, link-target, and blob comparison records in policy-probes/.
