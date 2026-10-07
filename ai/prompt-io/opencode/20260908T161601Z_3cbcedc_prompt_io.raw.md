---
model: openai/gpt-6-astra
service: opencode
timestamp: 2026-09-08T16:16:01Z
git_ref: 3cbcedcfdf61f633bc77a3b25b933b7b2b4dfb1d
diff_cmd: git diff 3cbcedcfdf61f633bc77a3b25b933b7b2b4dfb1d -- scripts/deploy.sh tests/deploy/shared-cases.sh README.md docs/shared-skills.md
---

## Generated Implementation

> `git diff 3cbcedcf -- scripts/deploy.sh`

Added clean tracked repository-skill relocation and relative Claude
adapters to migration. Generalized legacy hybrid link diagnosis and
repair while preserving shared whole-directory discovery links.
Preflight refuses conflicting payloads, unsafe links, ignored paths,
and changed tracked directory links. Default migration preserves the
index; explicit staging handles source-directory to symlink changes.

> `git diff 3cbcedcf -- tests/deploy/shared-cases.sh`

Added relocation, staging, refusal, hybrid repair, multi-provider safety,
and portable clone regression fixtures to the existing shell suite.

> `git diff 3cbcedcf -- README.md docs/shared-skills.md`

Documented source relocation, repair scope, refusal boundaries, and
interruption limitations. Runtime-state migration remains separate.

## Verification Output

Full deployment suite: 49 shell cases passed, including 42 embedded
Python contract tests. Shared-only suite: 10 shell cases passed.
Workflow-state suite: 14 tests passed. Codex discovers 21 shared skills.
Skill validation: 0 errors, 3 existing size warnings.
Deployment validation: 0 errors. Shell syntax and git diff checks passed.
