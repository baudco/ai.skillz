# Deploying `code-location-refs`

This is a provider-neutral, generic whole-directory skill. It creates no
runtime state and requires no provider-specific command.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use the portable method: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh code-location-refs <repo> \
  --provider <claude|opencode|all>
```

Provider destinations are `.claude/skills/code-location-refs` and
`.opencode/skills/code-location-refs`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update because skills are discovered at startup.
No `opencode.json` or `opencode.jsonc` mutation is needed or performed.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```
