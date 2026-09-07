# Shared skills across harnesses

`.agents/skills/` is the common discovery target for every harness
that can load it. Canonical workflows and resources live in `skills/`;
we maintain one implementation of each workflow. Harness-specific
commands and metadata adapt that implementation where necessary.

Use `--harness agents` for shared deployment. A harness controls
discovery, invocation, and tools; its model provider is configured
separately. Harness-specific aliases and metadata are described in
the harness notes below.

## Support and validation

Deployment support, native discovery, and successful workflow execution
are separate claims. Named harnesses are listed alphabetically;
the evidence records what was actually checked for each:

| Harness | Deployment approach | Validation in this change |
|---|---|---|
| Claude Code | Existing `.claude/skills/` and command adapters | Legacy deployment covered by regressions; shared discovery has not been verified here |
| Codex | Shared `.agents/skills/`; native skill invocation | All 21 skills discovered locally; invocation metadata and repository instructions checked; a local `commit-plan` generated |
| OpenCode | Native `.agents/skills/` discovery or existing `.opencode/skills/`; optional command wrappers | Shared command dependencies covered by deployment regressions; native discovery checked for the existing OpenCode layout |

### Adoption targets

Other harnesses, including Gemini CLI and GitHub Copilot, can use the
shared tree wherever their loaders support it. Native discovery and
workflow execution have not been validated for these targets here.
Before declaring support, verify discovery roots, directory symlinks,
resource resolution, invocation policy, and a representative composed
workflow. Record any required integration and the evidence separately.

A compatible discovery root does not guarantee identical metadata or
permissions. Invocation policy, tool permissions, hooks, credentials,
sandbox rules, and command syntax remain harness-specific. No installer
step selects models, copies authentication, or translates one harness's
permissions into another's.

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

OpenCode discovers `.agents/skills/` natively. To also install its
optional custom slash-command wrappers:

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
source anchors. It does not remove legacy discovery roots. Migration
is non-interactive: a conflicting local discovery directory is
reported as a blocker and refused rather than replaced. Resolve the
conflict manually before rerunning, and review the dry-run output
before applying changes.

Message archives, test references, configuration, and review context
use the [shared runtime contract](runtime-state.md). Fresh repositories
use `.ai/` configuration and `.ai/state/` artifacts; existing legacy
data keeps its legacy backend until an explicit runtime migration.
Consumer runtime migration remains separate from source deployment.
Use `runtime status` to inspect, `runtime migrate` to preview, and
`runtime migrate --apply <preview-sha256>` with the target repository
and reviewed digest to apply. These are `deploy.sh runtime` commands,
distinct from the non-interactive source-layout `migrate` above; see
the runtime contract for exact invocations and blockers.

Before removing an existing discovery layout, verify
the shared replacement with that consumer's installed harness.
Retain command wrappers wherever their explicit entry points are used.

## Validation and harness notes

Run `bash tests/deploy/test-deploy.sh` for deployment regressions, or
add `--shared-only` for shared-deployment and Codex probe regressions.
These exercise ownership, dependencies, portable clones, migration,
coexistence, and probe failures; they do not replace each harness's
native loader and workflow checks.

Consumer rollout should include representative workflows and locally
owned resources, not just successful installation. The notes below
distinguish discovery, invocation, metadata/permissions, and validation.

### Claude Code

- Discovery: the existing deployment uses `.claude/skills/`.
- Invocation: skill loading and `.claude/commands/` entry points use
  the canonical workflow bodies.
- Metadata and permissions: Claude-specific frontmatter remains
  harness-owned; it does not grant permissions in another harness.
- Validation: legacy deployment regressions pass; this change does
  not establish native shared discovery in Claude Code.

### Codex

- Discovery: shared directory links target `.agents/skills/`.
  `--harness codex` aliases `--harness agents` for the same destination.
- Invocation: use native skill invocation, such as `$commit-plan`.
- Metadata and permissions: optional `agents/openai.yaml` sidecars
  express invocation policy; tool permissions remain harness-owned.
- Validation: [Codex notes](codex-support.md) record versioned loader,
  symlink, metadata, and representative workflow evidence.

### OpenCode

- Discovery: project `.agents/skills/` and global `~/.agents/skills/`
  are native discovery locations alongside existing OpenCode layouts.
- Invocation: the native `skill` tool loads shared bodies. Optional
  `.opencode/commands/` wrappers provide custom slash commands.
- Metadata and permissions: OpenCode owns its skill/tool permissions;
  command wrappers do not translate another harness's grants.
- Validation: shared command dependencies are regression-tested;
  native discovery was checked for the existing OpenCode layout.
  [OpenCode documents shared discovery](https://opencode.ai/docs/skills/).
