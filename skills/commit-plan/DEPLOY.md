# Deploying `/commit-plan`

`commit-plan` is a provider-neutral generic skill which composes with the
hybrid `commit-msg` and `run-tests` skills. It writes generated messages and
ignored cached staging patches through `commit-msg`'s repository-local runtime
directories and uses `run-tests` for authoritative project-check selection.

## Deployment

Deploy the dependencies first:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-plan <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Use the normal `init` command first for a local symlink or portable submodule
anchor. `commit-plan` stops rather than degrading when either dependency is
missing. A repository-local run-tests harness reference is optional; the
canonical `run-tests` fallback remains available when it is absent.

OpenCode skill deployment installs its dependent command shim automatically.
The explicit command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command commit-plan <repo> \
  --provider opencode
```

Invoke `$commit-plan` in Codex, `/commit-plan` in Claude Code, or
`/commit-plan` through the OpenCode command adapter. Codex uses native
skills and needs no command shim. `--harness codex` and
`--harness agents` both deploy to `.agents/skills/`; a single shared
deployment can also serve OpenCode's skill loader.

Keep `commit-plan`, `commit-msg`, and `run-tests` deployed together. A
root `AGENTS.md` supplies repository guidance; it does not install skills.
See [Shared skills across harnesses](../../docs/shared-skills.md) for local validation
and the distinction between discovery, runtime permissions, and
verified workflow execution. Other compatible harnesses use the same
shared skill bodies with their own invocation mechanism.

Plan generation resolves project commands once and materializes boundaries in
private indexes without rewriting the user's index. Targeted checks remain in
their exact-tree execution boundaries, while the broadest documented safe
regression sequence runs once against the final boundary when one exists. A
check successfully pre-executed against unchanged evidence is not rendered
twice.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update.
