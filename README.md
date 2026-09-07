# `ai.skillz`

Reusable AI agent skills with one canonical workflow per skill and
shared `.agents/skills/` deployment for compatible harnesses. Codex and
OpenCode can use that shared tree; existing Claude Code and OpenCode
adapters remain available. Other harnesses can adopt the same tree
where their discovery and invocation mechanisms support it.

Skills follow the
[Agent Skills specification](https://agentskills.io/specification).
See the [support and validation matrix](docs/shared-skills.md) for the
distinction between shared architecture and verified harness behavior.

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
| `commit-plan` | Multi-commit orchestration using `commit-msg` messages |
| `pr-msg` | PR description generation |
| `code-review` | Read-only, Python-focused review with structured findings |
| `code-nav-refs` | Editor-jumpable repository file and line citations |
| `code-review-changes` | Apply PR review feedback |
| `dep-supersede-scan` | Flag dep bumps that supersede bot PRs / resolve alerts |
| `run-tests` | Shared test workflow with repository-owned harness guidance |
| `resolve-conflicts` | Merge conflict resolution |
| `open-wkt` / `close-wkt` | Git worktree lifecycle |
| `opencode-cleaning` | Safely preview and remove stale OpenCode forks |
| `plan-io` | Plan file conventions |
| `prompt-io` | AI prompt I/O provenance logging |
| `inter-skill-review` | Cross-skill consistency |
| `gish` | Local-file-first forge transport, including approved reviews |
| `git-mgmt` | Coordinate Git branches, worktrees, and stacked history safely |
| `harness-perf` | Diagnose CPU, memory, latency, and hangs in AI coding harnesses |
| `taken-export` | Export repository work as Taken-compatible Org tasks |
| `yt-url-lookup` | YouTube URL resolution |

## Deployment

Portable deployment uses a provider-neutral source anchor at
`<repo>/.ai/ai.skillz`. Provider discovery trees use relative links to that
anchor in portable mode and ignored absolute links in local mode:

| Discovery target | Skills | Commands |
|----------|--------|----------|
| Claude Code | `.claude/skills/` | `.claude/commands/` |
| OpenCode | `.opencode/skills/` or shared `.agents/skills/` | `.opencode/commands/` |
| Shared (compatible harnesses) | `.agents/skills/` | Harness-specific invocation |

Canonical skill prose is shared. Harness-specific command shims and
invocation metadata remain small adapters. Metadata is not a portable
permission grant: each harness retains its own tool permissions,
sandbox, credentials, and model provider configuration. See
[Shared skills across harnesses](docs/shared-skills.md) for discovery and rollout details.

Initialize the anchor, then select shared deployment or a legacy adapter:

```bash
# Local development: .ai/ai.skillz is an ignored absolute symlink.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

# Portable deployment: .ai/ai.skillz is a versioned git submodule.
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh <skill> <repo> \
  --harness agents

# Global single-skill deployment; no target repository or staging.
bash /path/to/ai.skillz/scripts/deploy.sh <skill> --global
bash /path/to/ai.skillz/scripts/deploy.sh <skill> --global --harness agents
```

`--provider claude` writes `.claude` links, `--provider opencode`
writes `.opencode` links, and `--provider all` writes both. The new
`--harness` spelling is an alias for `--provider`. Select `agents` or
`codex` to deploy one shared `.agents/skills/` tree. Deployment `all`
keeps its legacy meaning; status `all` includes the shared tree. Local symlink
deployment creates ignored absolute provider links. Submodule deployment
creates trackable relative links through the anchor. Nothing is staged unless
`--stage` is explicitly supplied, and the script never commits.
Shared deployment into this source repository uses trackable relative
links directly to `skills/`, without needing an anchor to itself.

OpenCode skill deployment automatically installs every OpenCode command whose
manifest dependency names that skill. Use `--no-command` for an intentional
skill-only deployment. Command destinations are preflighted with skill
destinations before any mutation.

Skill and command deployment defaults to `--provider claude`, `init`
defaults to `--method submodule`, and `status` defaults to
`--provider all`. Portable deployments initialize an anchor explicitly.
When no anchor exists, an omitted method or `--method symlink` uses ignored
absolute links; `--direct` remains an explicit compatibility alias.

Global skill deployment links beneath `~/.claude/skills/` by default,
or `~/.agents/skills/` with `--harness agents` or `--harness codex`.
It converts missing destinations or byte-identical
canonical copies, preserves non-canonical files in hybrid directories, and
refuses divergent content. An existing selected global skills-root link to this
checkout's canonical `skills/` tree is accepted as an already-complete global
deployment; other symlinked parent directories are refused.

Shared `.agents` skills use whole-directory links, which also meet
Codex's discovery requirements. In legacy discovery trees, generic skills use
whole-directory links, while hybrid skills such as `commit-msg` and
`pr-msg` link only declared files and resources. Repository-owned
runtime state stays outside the shared source directories. The [shared runtime contract](docs/runtime-state.md) uses `.ai` for
fresh repositories. Existing `.claude/` state needs explicit migration; source deployment does not migrate or delete
message archives, configuration, review context, or worktree state.
In legacy layouts, `run-tests` is hybrid: its canonical `SKILL.md` is
linked while each repository owns `test-harness-reference.md`. Shared
deployment keeps that repository-owned reference at its existing path.

### Commands

Provider-specific reusable assets live under `providers/`. For example,
the canonical OpenCode `/commit-msg` shim is
`providers/opencode/commands/commit-msg.md`; every user-facing workflow command
uses the same layout. Local deployment links `.opencode/commands/<name>.md`
directly to the
canonical provider asset and ignores that absolute link. Portable deployment
uses a trackable relative link through `.ai/ai.skillz`. This repository
self-hosts with tracked relative links from `.opencode/commands/` to
`providers/opencode/commands/`.

```bash
# Installs both the OpenCode skill and its dependent command shim.
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --provider opencode

# Explicit command deployment remains available for repair or migration.
bash /path/to/ai.skillz/scripts/deploy.sh command commit-msg <repo> \
  --provider opencode
```

OpenCode discovers `.opencode/skills/` and `.opencode/commands/`
without configuration changes. The deploy and migration commands do not
edit `opencode.json` or `opencode.jsonc`; `status` reports unportable
`skills.paths` entries for manual review. Quit and restart OpenCode after
deploying or updating skills or commands because discovery occurs at
startup.

OpenCode command shims are provided for user-invoked workflows: code review
and remediation, commit/PR messages, worktree lifecycle, Git management,
conflict resolution, forge operations, dependency supersedence scans, test
runs, harness diagnostics, OpenCode cleanup, Taken export, and YouTube URL
lookup. Support skills such as `plan-io`, `prompt-io`, `py-codestyle`, and
`inter-skill-review` remain skill-only.

### Maintenance and migration

```bash
# Inspect the anchor, shared and legacy trees, and broken links,
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

For configuration resolution and explicit runtime migration, see
[the runtime contract](docs/runtime-state.md).
Run `python3 -B tests/deploy/test-workflow-state.py` for migration,
conflict, index-preservation, and worktree-isolation regressions.
