---
model: openai/gpt-6-astra
service: opencode
session: repo-skill-migration-20260908
timestamp: 2026-09-08T16:16:01Z
git_ref: 3cbcedcfdf61f633bc77a3b25b933b7b2b4dfb1d
scope: code
substantive: true
raw_file: 20260908T161601Z_3cbcedc_prompt_io.raw.md
---

## Prompt

The human first requested read-only existing-work discovery for two
consumer deployment gaps observed in piker PR 93: tracked repository
skills remained under Claude discovery, and a stale whole-directory
commit-plan link was diagnosed as unhealthy but refused by deployment.

The human then explicitly authorized implementation:
"ok let's have at it then in that wkt in ai.skillz/ ya?"
The requested destination was wkts/repo_skill_migration_safety, on a new
wkt/repo_skill_migration_safety branch based on the verified shared-skills
line. Instructions required safe preflight, preservation of unrelated
and divergent contents, default index isolation, regression coverage,
deployment documentation, and provenance. No commits, pushes, rebases,
resets, remote PR edits, or task-marker transitions were authorized.

## Response Summary

Created the isolated worktree at 3cbcedcf. Implemented tracked clean
repository-skill relocation with relative Claude adapters and recognized
legacy hybrid link repair. Added regression fixtures for safety,
staging, repeatability, shared coexistence, and fresh portable clones.
Documented refusal and interruption boundaries.

## Files Changed

- scripts/deploy.sh: migration, preflight, repair, status, and help.
- tests/deploy/shared-cases.sh: four new regression groups.
- README.md: deployment migration overview.
- docs/shared-skills.md: detailed migration and repair contract.

## Human Edits

The human supplied the consumer failure cases and selected the worktree,
scope, safety requirements, and no-history-mutation boundary. These are
human-directed design constraints. No subsequent manual source edits
were observed during generation; the result remains pending review.

## Verification

Used the repository's documented shell deployment suite. No local
test-harness reference exists. Python subprocesses used the inherited
Python 3.13 environment; tests load this worktree's source and use
disposable fixtures, without installing dependencies.

49 deployment shell cases and 42 embedded Python tests passed;
14 workflow-state tests passed. Native Codex discovered all 21 shared
skills. Skill validation had zero errors and three pre-existing length
warnings. Deployment validation, shell syntax, and diff checks passed.
