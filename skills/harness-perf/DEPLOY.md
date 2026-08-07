# Deploying `/harness-perf`

This is a provider-neutral, generic whole-directory skill. Its bundled
references include reusable OpenCode diagnostics and a dated OpenCode case
study; it creates no runtime state by default.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use the portable method: --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh harness-perf <repo> \
  --provider <claude|opencode|all>
```

Provider destinations are `.claude/skills/harness-perf` and
`.opencode/skills/harness-perf`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update because skills are discovered at startup.
No `opencode.json` or `opencode.jsonc` mutation is needed or performed.

## Optional Runtime Reports

The skill writes nothing during ordinary diagnosis. If a user explicitly
requests a durable report, it may create a sanitized record under:

```text
.ai/harness-perf/YYYY-MM-DD-<harness>.md
```

Decide with the target repository whether those reports should be tracked.
They can contain machine paths, process metadata, or session identifiers even
after prompt and tool content is excluded.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

## Prerequisites

- Process inspection tools appropriate to the host operating system.
- Permission to inspect the target harness process.
- Optional profilers only when already installed and explicitly authorized.
