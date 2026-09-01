# Deploying `/code-review`

The provider-neutral skill is a generic whole-directory deployment. Review
reports are optional worktree-local runtime state outside the skill directory.

## Managed Deployment

The deployment script currently manages Claude Code and OpenCode consumers:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

bash /path/to/ai.skillz/scripts/deploy.sh code-review <repo> \
  --provider <claude|opencode|all>
```

Use `--method submodule` after portable initialization. Provider destinations
are `.claude/skills/code-review` and `.opencode/skills/code-review`. Local
links are absolute and ignored; portable links are relative and trackable.
Nothing is staged unless `--stage` is explicitly supplied.

OpenCode also needs its command shim:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command code-review <repo> \
  --provider opencode
```

Quit and restart OpenCode after deployment or update. The command and skill
load at startup; deployment does not mutate consumer `opencode.json` files.

## Other Agent Skills Consumers

The same `skills/code-review/` directory follows the Agent Skills standard.
Link or copy the whole directory into the provider's supported project skill
location:

| Harness | Project skill location | Preferred entry point |
|---|---|---|
| Codex | `.agents/skills/code-review/` | Native `/review` or explicit skill request |
| Gemini CLI | `.agents/skills/code-review/` or `.gemini/skills/code-review/` | Provider command or explicit skill request |
| GitHub Copilot | `.github/skills/code-review/` or `.agents/skills/code-review/` | Native Copilot code review |

Keep provider commands, agents, permission rules, hooks, and publication
credentials outside the shared skill. Native review commands may have the
same display name; use the provider's native entry point when it already owns
that command and let it consume the skill instructions.

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

`/run-tests` is optional and owns runtime test execution. Deploy it when a
review should be able to confirm findings with project-specific tests.
`/py-codestyle` is optional and, when deployed by the target repository, owns
formatting for Python replacement snippets and suggested patches.
`/code-review-changes` remains the separate workflow for applying and
publishing responses to existing remote review feedback.
