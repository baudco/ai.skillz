# Deploying `layered-design`

This provider-neutral skill has one shared `SKILL.md` and no runtime
assets or provider-specific command. Deploy it from the canonical
`ai.skillz` checkout through the manifest:

```xsh
./scripts/deploy.sh layered-design /path/to/repo --harness all
./scripts/deploy.sh layered-design /path/to/repo --harness agents
```

The first command covers Claude and OpenCode. The second installs the
shared `.agents/skills/` discovery link used by Codex and compatible
harnesses. No workflow state is created by deployment.
