# Repository instructions

Canonical skill bodies and resources live in `skills/`. Keep workflow
logic there so harnesses share one implementation. Harness-specific
commands belong under `providers/`; optional Codex skill metadata lives
in each skill's `agents/openai.yaml`.

For substantial subsystem design or refactors, use the shared
`layered-design` skill to establish the user workflow, public
contract, vocabulary, and module boundaries before adding helpers.

Use `scripts/deploy.sh` and `deploy-manifest.conf` for deployment.
`.agents/skills/` is a discovery tree, and `.ai/ai.skillz` is the
consumer source anchor. Skill metadata does not configure model
providers, credentials, tool permissions, or sandbox policy.

Preserve user-owned task and checklist states unless the user requests
the exact transition. Implementation completion does not imply human
acceptance. Preserve runtime files and unrelated worktree changes.

Validate skill changes with `bash scripts/validate-skills.sh` and
deployment changes with `bash tests/deploy/test-deploy.sh`. The shared
deployment cases can also run with `--shared-only`. Run
`bash scripts/validate-deployment.sh .` to inspect this checkout.

Hard-wrap ordinary prose near 69 columns, keeping code references and
links intact. Resolve supporting files relative to the skill being
read, rather than the shell's current directory.
