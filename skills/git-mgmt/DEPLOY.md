# Deploying `/git-mgmt`

This is a generic whole-directory skill with no per-repository state.

## Deployment

```bash
# Local anchor: ignored .ai/ai.skillz symlink to this checkout.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# Portable anchor: version-pinned .ai/ai.skillz submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh git-mgmt <repo> \
  --provider <claude|opencode|all>
```

The provider destinations are `.claude/skills/git-mgmt` and
`.opencode/skills/git-mgmt`. Local mode uses ignored absolute links;
submodule mode uses trackable relative links through `.ai/ai.skillz`.

Track provider links, `.gitmodules`, and the anchor gitlink only in submodule
mode. Local provider links remain ignored, and deployment stages only when
`--stage` is explicitly supplied. Quit and restart OpenCode after deployment
or update because skill discovery occurs at startup.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

## Prerequisites

- `git` CLI
- Deployed `resolve-conflicts` companion for authorized conflict resolution
- Optional deployed `gish` skill for provider-neutral forge inspection

Fresh forge inspection additionally requires an adapter supported by `gish`,
an authenticated provider client, and explicit current-prompt network
authorization. Without those capabilities, `/git-mgmt` is limited to clearly
labeled local/prospective inspection.

The canonical provider overlays currently support Claude Code and OpenCode.
Other agentskills.io consumers may read the provider-neutral workflow, but
must supply equivalent Git, local-read, and separately authorized forge
capabilities; the frontmatter tool grants are not portable permission policy.
