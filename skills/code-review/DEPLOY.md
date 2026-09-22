# Deploying `/code-review`

The provider-neutral skill is a generic whole-directory deployment. Review
reports are optional worktree-local runtime state outside the skill directory.

## Managed Deployment

The deployment script manages shared `.agents` discovery and the
existing Claude Code and OpenCode adapters:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

bash /path/to/ai.skillz/scripts/deploy.sh code-review <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Use `--method submodule` after portable initialization. Provider destinations
are `.claude/skills/code-review`, `.opencode/skills/code-review`,
and shared `.agents/skills/code-review`. Local
links are absolute and ignored; portable links are relative and trackable.
Nothing is staged unless `--stage` is explicitly supplied.

OpenCode skill deployment installs its dependent command shim automatically.
The explicit command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command code-review <repo> \
  --provider opencode
```

Quit and restart OpenCode after deployment or update. The command and skill
load at startup; deployment does not mutate consumer `opencode.json` files.

## Other Agent Skills Consumers

The same `skills/code-review/` directory follows the Agent Skills
standard. Prefer `--harness agents` wherever the target harness can
load the shared tree. Codex's `--harness codex` selector is an alias
for that deployment; invoke its installed skill with `$code-review`.
OpenCode can use shared skills with its `/code-review` command adapter.

Other harnesses, including Gemini CLI and GitHub Copilot, are adoption
targets. Verify their current discovery roots, directory-link support,
and explicit skill invocation before declaring support. Their native
review features do not by themselves establish use of this workflow.
See the [support and validation matrix](../../docs/shared-skills.md).

Keep provider commands, agents, permission rules, hooks, and publication
credentials outside the shared skill. Native review commands may have the
same display name. A built-in review command is not guaranteed to load
this skill; request the installed skill explicitly when its workflow
is required.

## Runtime State

Chat-only reviews write nothing. Explicit JSON exports use:

```text
.ai/code-review/reports/
```

Managed deployment adds this path to a bounded `.gitignore` block. Reports
remain ephemeral and must not be staged or published by this skill.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

`/test-design` is optional and owns detailed test-adequacy analysis and
authored regression coverage. Its required dependency is `/run-tests`.
`/run-tests` is optional and owns runtime test execution. Deploy it when a
review should be able to confirm findings with project-specific tests.
`/py-codestyle` is optional and, when deployed by the target repository, owns
formatting for Python replacement snippets and suggested patches.
`/gish` is the preferred optional transport for human-approved top-level
review publication:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh gish <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Local review remains available without `gish`. Publication must stop or obtain
new explicit approval for a disclosed direct-provider fallback when the
selected `gish` backend cannot publish reviews.
`/code-review-changes` remains the separate workflow for applying and
publishing responses to existing remote review feedback.
