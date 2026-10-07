---
model: openai/gpt-6-astra
service: opencode
timestamp: 2026-09-08T21:24:03Z
git_ref: 3cbcedcfdf61f633bc77a3b25b933b7b2b4dfb1d
diff_cmd: git diff 3cbcedcf -- scripts/deploy.sh tests/deploy/shared-cases.sh README.md docs/shared-skills.md
---

## Generated Revision

> `git diff 3cbcedcf -- scripts/deploy.sh`

Added explicit per-invocation --repo-skills move|preserve consent.
Inventory includes unmanaged disk entries, not only tracked skills.
Absent choice stops dry-run and apply with affected paths and an
agent-ready prompt. Move retains clean tracked-tree preflight;
preserve reports sources as not migrated. Neither bypasses canonical
link safeguards. The earlier implicit relocation policy is superseded.

> `git diff 3cbcedcf -- tests/deploy/shared-cases.sh`

Updated successful relocation tests to pass explicit consent. Added
no-choice, untracked/ignored definition, preservation, invalid-option,
and tracked canonical-link guard regression coverage.

> `git diff 3cbcedcf -- README.md docs/shared-skills.md`

Documented decision-needed status, move/preserve choices, no implicit
consent from dry-run, and independent canonical safety failures.

## Verification

Shared deployment suite: 11 cases passed. Full deployment suite: 50
cases and 42 embedded Python tests passed. Skill validator: zero
errors and three existing size warnings. Deployment validator: zero
errors. Syntax and diff whitespace checks passed.

Eight fresh detached historical scenarios were exercised. At the
pre-deployment base, absent consent halts and both explicit choices
still refuse the tracked absolute commit-msg link without mutation.
At the post-deployment Git base, preserve leaves four sources in
place, and move reproduces ten PR93 skill blobs/modes plus four
relative adapters. Repeats preserve filesystem and index evidence.

The raw post-deployment Git fixture lacks an ignored canonical
commit-msg link, so whole-deployment validation initially failed.
This is retained as evidence, not reported as a relocation failure.
A separate fixture bootstrapped canonical deployment, still refused
absent move consent, then passed explicit migration, idempotence,
PR93 comparison, and whole-deployment validation. Private-index
--stage covered exactly 24 source/destination paths without changing
the fixture's real index.
