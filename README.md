# `ai.skillz`

Reusable AI agent skills for
[`claude-code`](https://github.com/anthropics/claude-code) and
[`opencode`](https://github.com/anomalyco/opencode), conforming to the
[agentskills.io](https://agentskills.io/specification)
specification.

Extracted from real-world Python projects
([`tractor`](https://github.com/goodboy/tractor),
[`piker`](https://github.com/pikers/piker),
[`modden`](https://github.com/goodboy/modden)) and
generalized for cross-repo deployment.

## Skills

| Skill | Description |
|-------|-------------|
| `py-codestyle` | Python code style conventions |
| `commit-msg` | Git commit message generation |
| `pr-msg` | PR description generation |
| `code-review-changes` | Apply PR review feedback |
| `dep-supersede-scan` | Flag dep bumps that supersede bot PRs / resolve alerts |
| `run-tests` | Shared test workflow with repository-owned harness guidance |
| `resolve-conflicts` | Merge conflict resolution |
| `open-wkt` / `close-wkt` | Git worktree lifecycle |
| `plan-io` | Plan file conventions |
| `prompt-io` | AI prompt I/O provenance logging |
| `inter-skill-review` | Cross-skill consistency |
| `gish` | Git-over-SSH transport |
| `taken-export` | Export repository work as Taken-compatible Org tasks |
| `yt-url-lookup` | YouTube URL resolution |

## Deployment

Portable deployment uses a provider-neutral source anchor at
`<repo>/.ai/ai.skillz`. Provider discovery trees use relative links to that
anchor in portable mode and ignored absolute links in local mode:

| Provider | Skills | Commands |
|----------|--------|----------|
| Claude Code | `.claude/skills/` | `.claude/commands/` |
| OpenCode | `.opencode/skills/` | `.opencode/commands/` |

Initialize the anchor, then deploy a skill to one or both providers:

```bash
# Local development: .ai/ai.skillz is an ignored absolute symlink.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

# Portable deployment: .ai/ai.skillz is a versioned git submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh <skill> <repo> \
  --provider <claude|opencode|all>
```

`--provider claude` writes `.claude` links, `--provider opencode`
writes `.opencode` links, and `--provider all` writes both. Local symlink
deployment creates ignored absolute provider links. Submodule deployment
creates trackable relative links through the anchor. Nothing is staged unless
`--stage` is explicitly supplied, and the script never commits.

Skill and command deployment defaults to `--provider claude`, `init`
defaults to `--method submodule`, and `status` defaults to
`--provider all`. Portable deployments initialize an anchor explicitly.
When no anchor exists, an omitted method or `--method symlink` uses ignored
absolute links; `--direct` remains an explicit compatibility alias.

Generic skills are linked as whole directories. Hybrid skills such as
`commit-msg` and `pr-msg` keep local directories for generated state and
link only canonical files and resources. Existing runtime paths under
`.claude/` remain in place; source deployment does not migrate or delete
message archives, configuration, review context, or worktree state.
`run-tests` is hybrid: its canonical `SKILL.md` is linked while each
repository owns `test-harness-reference.md`.

### Commands

Provider-specific reusable assets live under `providers/`. For example,
the canonical OpenCode `/commit-msg` shim is
`providers/opencode/commands/commit-msg.md`; Taken and Run shims use the same
layout. Local deployment links `.opencode/commands/<name>.md` directly to the
canonical provider asset and ignores that absolute link. Portable deployment
uses a trackable relative link through `.ai/ai.skillz`. This repository
self-hosts with tracked relative links from `.opencode/commands/` to
`providers/opencode/commands/`.

```bash
# The command dependency is enforced: deploy the OpenCode skill first.
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider opencode
bash /path/to/ai.skillz/scripts/deploy.sh command commit-msg <repo> \
  --provider opencode
```

OpenCode discovers `.opencode/skills/` and `.opencode/commands/`
without configuration changes. The deploy and migration commands do not
edit `opencode.json` or `opencode.jsonc`; `status` reports unportable
`skills.paths` entries for manual review. Quit and restart OpenCode after
deploying or updating skills or commands because discovery occurs at
startup.

### Maintenance and migration

```bash
# Inspect the anchor, both provider trees, broken links, legacy layouts,
# command shims, and unportable OpenCode skills.paths entries.
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all

# Preview every legacy-layout migration change, then apply it.
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>

# Advance a submodule anchor, optionally to a specific ref.
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]

# Validate the manifest, deployed paths, status, and Git index.
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Always review migration output first. Migration preserves hybrid local
state and unrelated files. For a local symlink anchor, update the source
checkout directly instead of using `update`.

`validate-deployment.sh` validates manifest sources and command
dependencies, runs deployment status, rejects committed absolute
provider links, and inspects the Git index for tracked or staged runtime
state such as message archives, session configuration, review context,
worktrees, and command session files.

The read-only
[consumer deployment inventory](docs/deployment-consumer-inventory.md)
records the observed migration state of known consumers and recommended
follow-up commands.

Each active skill has a `DEPLOY.md` with its prerequisites and any
skill-specific local setup.

## License

AGPL-3.0 — see [`LICENSE`](./LICENSE).

Commercial licenses available from
[`baudco`](https://github.com/baudco) for proprietary
use cases. See [`LICENSING.md`](./LICENSING.md) for
details.
