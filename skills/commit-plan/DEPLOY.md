# Deploying `/commit-plan`

`commit-plan` is a provider-neutral hybrid skill which composes with the
hybrid `commit-msg` and `run-tests` skills. Its `scripts/plan-exec.py` asset
executes pinned boundary specifications without duplicating commits after a
partial or complete run. The skill writes generated messages, specifications
and cached staging patches through `commit-msg`'s ignored repository-local
runtime directories and uses `run-tests` for project-check selection.

## Deployment

Deploy the dependencies first:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --provider <claude|opencode|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider <claude|opencode|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-plan <repo> \
  --provider <claude|opencode|all>
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

Claude Code and other Agent Skills consumers invoke the generic skill directly
as `/commit-plan`; no provider command asset is required for them. Use each
harness's normal project or global Agent Skills directory for `commit-plan`,
`commit-msg`, and `run-tests`, preserving the dependency set:

| Harness | Skill location |
|---|---|
| Claude Code | `.claude/skills/` or `~/.claude/skills/` |
| OpenCode | `.opencode/skills/` or configured global skill discovery |
| Codex | `.agents/skills/` |
| Gemini CLI | `.agents/skills/` or `.gemini/skills/` |
| GitHub Copilot | `.agents/skills/` or `.github/skills/` |

Plan generation resolves project commands once and materializes boundaries in
private indexes without rewriting the user's index. Targeted checks remain in
their exact-tree execution boundaries, while the broadest documented safe
regression sequence runs once against the final boundary when one exists. A
check successfully pre-executed against unchanged evidence is not rendered
twice.

The rendered command block pins one generated JSON specification by SHA-256,
runs the executor's read-only `--preflight` and `--show` modes, then invokes
`--execute <ordinal>` for each boundary. The executor recognizes an exact
completed parent/tree prefix before touching the index, checks, editor or
hooks. Repeating the complete block therefore skips committed boundaries and
resumes the first pending boundary; unexpected history stops as divergence.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update.
