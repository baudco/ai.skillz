# Deploying `/commit-plan`

`commit-plan` is a provider-neutral generic skill which composes with the
hybrid `commit-msg` skill. It writes generated messages and ignored cached
staging patches through `commit-msg`'s repository-local runtime directories.

## Deployment

Deploy the dependency first:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider <claude|opencode|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-plan <repo> \
  --provider <claude|opencode|all>
```

Use the normal `init` command first for a local symlink or portable submodule
anchor. `commit-plan` stops rather than degrading when `commit-msg` is missing.

OpenCode skill deployment installs its dependent command shim automatically.
The explicit command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command commit-plan <repo> \
  --provider opencode
```

Claude Code and other Agent Skills consumers invoke the generic skill directly
as `/commit-plan`; no provider command asset is required for them. Use each
harness's normal project or global Agent Skills directory for both
`commit-plan` and `commit-msg`, preserving the dependency as a pair:

| Harness | Skill location |
|---|---|
| Claude Code | `.claude/skills/` or `~/.claude/skills/` |
| OpenCode | `.opencode/skills/` or configured global skill discovery |
| Codex | `.agents/skills/` |
| Gemini CLI | `.agents/skills/` or `.gemini/skills/` |
| GitHub Copilot | `.agents/skills/` or `.github/skills/` |

Plan generation resolves project commands once and materializes boundaries in
private indexes without rewriting the user's index. Targeted checks remain in
their exact-tree execution boundaries, while the full suite runs once against
the final boundary unless repository evidence requires otherwise. A check
successfully pre-executed against unchanged evidence is not rendered twice.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update.
