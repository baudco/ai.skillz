# Shared skills across harnesses

`.agents/skills/` is the common discovery target for every harness
that can load it. Canonical workflows and resources live in `skills/`;
we maintain one implementation of each workflow. Harness-specific
commands and metadata adapt that implementation where necessary.

Use `--harness agents` for shared deployment. `--harness codex` is an
alias for the same destination, not a separate implementation or a
choice of model provider. A harness controls discovery, invocation,
and tools; its model provider is configured separately.

## Support and validation

Deployment support, native discovery, and successful workflow execution
are separate claims. The current evidence is:

| Harness | Deployment approach | Validation in this change |
|---|---|---|
| Codex | Shared `.agents/skills/`; native skill invocation | All 21 skills discovered locally; invocation metadata and repository instructions checked; a local `commit-plan` generated |
| OpenCode | Shared skills with optional `.opencode/commands/` adapters, or existing `.opencode/skills/` | Shared command dependencies covered by deployment regressions; native discovery checked for the existing OpenCode layout |
| Claude Code | Existing `.claude/skills/` and command adapters | Legacy deployment covered by regressions; shared discovery has not been verified here |
| Other harnesses, including Gemini CLI and GitHub Copilot | Use the shared tree wherever their loaders support it; retain an adapter where required | Adoption targets; no native loader or workflow validation in this change |

The intent is to extend shared deployment to other compatible harnesses,
not create a Codex-only skill collection. Before declaring another
harness supported, verify its discovery roots, directory symlinks,
resource resolution, invocation policy, and a representative composed
workflow. Document any required adapter and the evidence separately.

A compatible discovery root does not guarantee identical metadata or
permissions. `allowed-tools`, Codex's `agents/openai.yaml`, hooks,
credentials, sandbox rules, and command syntax remain harness-specific.
No installer step selects models, copies authentication, or translates
one harness's permissions into another's.

## Deploy the shared tree

From this source checkout:

```bash
bash scripts/deploy.sh all . --harness agents
bash scripts/deploy.sh status .
bash scripts/validate-deployment.sh .
```

For another repository, initialize the source anchor and deploy:

```bash
# Local development: ignored links to this source checkout.
bash scripts/deploy.sh init <repo> --method symlink
bash scripts/deploy.sh all <repo> --harness agents

# For portable deployment, use --method submodule at initialization.
```

Shared links within this source repository point relatively to
`skills/`. Consumer symlink installations use ignored absolute links;
submodule installations use trackable relative links through
`.ai/ai.skillz`. All shared skills use whole-directory links, including
skills with legacy hybrid layouts. Repository-owned runtime files
remain outside the shared source directories.

`--provider` remains an alias for `--harness`. Existing deployment
`all` still means Claude plus OpenCode; it does not mean every harness
or include shared deployment. Status `all` also audits `.agents`.
Nothing is staged without `--stage`, and the installer never commits.

Global single-skill deployment uses the same neutral selector:

```bash
bash scripts/deploy.sh <skill> --global --harness agents
```

This installs beneath `~/.agents/skills/`. Existing parent symlinks
owned by Dotrc or another installer are refused unless they point
exactly at this checkout's canonical skill tree. Choose one owner for
that root. Status audits project roots, not the full global registry.

## Coexistence and migration

OpenCode can consume shared skills while retaining command adapters:

```bash
bash scripts/deploy.sh all <repo> --harness agents
bash scripts/deploy.sh command all <repo> --harness opencode
```

Command dependency checks accept a healthy shared skill when no
OpenCode-specific deployment exists for that name. A broken or
divergent explicit deployment remains an error. Status reports
same-source aliases and flags divergent same-name definitions; it
does not assume loaders merge them. See
[OpenCode skill discovery](https://opencode.ai/docs/skills/).

The `migrate` command recognizes shared deployments when normalizing
source anchors. It does not remove legacy discovery roots. Review its
dry run before applying it. Existing local discovery directories are
refused for manual reconciliation rather than replaced automatically.

Message archives, test references, configuration, and review context
retain their existing paths, including `.claude/` locations. Runtime
migration and deployment across consumer repositories are separate
follow-up work. Keep harness-specific discovery adapters until their
shared replacements have been verified.

## Validation and harness notes

Run `bash tests/deploy/test-deploy.sh` for deployment regressions, or
add `--shared-only` for the six shared-deployment cases. These exercise
ownership, dependencies, portable clones, migration, and coexistence;
they do not replace each harness's native loader and workflow checks.

[Codex notes](codex-support.md) describe its invocation metadata,
loader behavior, and optional native discovery test. Add equivalent
notes and checks as other harnesses are validated. Consumer rollout
should include representative workflows and locally owned resources,
not just successful installation.
