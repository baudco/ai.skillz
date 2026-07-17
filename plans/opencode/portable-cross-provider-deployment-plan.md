# Plan: portable cross-provider skill deployment

## Context

`ai.skillz` currently deploys skills and commands through Claude-owned
paths:

- shared source or submodule under `.claude/ai.skillz/`
- skill links under `.claude/skills/`
- command links under `.claude/commands/`
- per-skill runtime state under `.claude/`

OpenCode can load the canonical `skills/` tree through `skills.paths`,
but consumer repos such as `lns` currently use an absolute checkout
path (`/home/goodboy/repos/ai.skillz/skills`). That works for one
workstation but is not clone-portable. Committing an absolute skill
symlink has the same problem.

The temporary arrangement remains supported while this plan is
deferred. Do not migrate existing consumers until the deployment
contract and fixture tests below are implemented.

## Goals

- Keep canonical skill content provider-neutral and stored once.
- Make committed deployment artifacts independent of usernames and
  checkout locations.
- Support OpenCode and Claude Code without requiring either provider's
  config directory to own the shared source checkout.
- Preserve local-development convenience through untracked symlinks.
- Support version-pinned portable deployment through a git submodule.
- Preserve existing per-repo skill state and archives during source
  deployment migration.
- Give deploy, status, update, and validation commands one consistent
  model across providers.

## Non-goals

- Do not move `.claude/skills/<name>/msgs/`, `conf.toml`, review
  context, or other persisted runtime state in the first migration.
- Do not rewrite historical plans that document the old deployment.
- Do not require arbitrary mutation of existing `opencode.json` or
  `opencode.jsonc` files.
- Do not remove the existing Claude deployment path until all known
  consumer repos have migrated.

## Target layout

Use a provider-neutral source anchor in every consumer repo:

```text
.ai/
└── ai.skillz/                         # symlink or git submodule

.claude/
├── commands/
└── skills/
    └── commit-msg/
        ├── SKILL.md -> ../../../.ai/ai.skillz/skills/commit-msg/SKILL.md
        ├── conf.toml                  # existing local state
        └── msgs/                      # existing local state

.opencode/
├── commands/
│   └── commit-msg.md -> ../../.ai/ai.skillz/providers/opencode/commands/commit-msg.md
└── skills/
    └── commit-msg/
        └── SKILL.md -> ../../../.ai/ai.skillz/skills/commit-msg/SKILL.md
```

OpenCode discovers `.opencode/skills/` and `.opencode/commands/`
without a `skills.paths` edit. Claude Code continues to discover
`.claude/skills/` and `.claude/commands/`. Both provider trees point
at the same canonical skill content.

Generic skills that do not need local state can use whole-directory
links:

```text
.claude/skills/py-codestyle
  -> ../../.ai/ai.skillz/skills/py-codestyle
.opencode/skills/py-codestyle
  -> ../../.ai/ai.skillz/skills/py-codestyle
```

Hybrid skills such as `commit-msg` and `pr-msg` retain provider-local
directories and link only canonical files or resource directories.

## Source-anchor modes

### Local development

`.ai/ai.skillz` is an absolute symlink to a developer checkout. The
anchor itself is ignored and never committed. Provider links remain
relative to the anchor, so no absolute paths appear in tracked config
or symlinks.

Expected tracked artifacts:

- provider command shims, when copied instead of linked
- relative provider skill links only when the target deliberately
  commits a shared local-layout contract
- `.gitignore` entries for the local anchor and runtime state

### Portable submodule

`.ai/ai.skillz` is a git submodule. Prefer a relative submodule URL
such as `../ai.skillz.git` so SSH/HTTPS transport follows the parent
repository's remote.

Expected tracked artifacts:

- `.gitmodules`
- `.ai/ai.skillz` gitlink
- relative links under each enabled provider directory
- provider command shims
- runtime-state ignore entries

The relative provider links are identical in local and submodule
modes. Only the anchor type differs.

## Provider assets in `ai.skillz`

Add a provider-owned configurable tree without duplicating generic
skills:

```text
providers/
└── opencode/
    └── commands/
        └── commit-msg.md
```

Move the reusable OpenCode `/commit-msg` shim from this repository's
project-local `.opencode/commands/` definition into that provider
tree, then deploy or link it back into `.opencode/commands/` for this
repo and consumers.

Keep provider assets thin. They should invoke canonical skills rather
than repeat workflow instructions. Add future provider-specific agents,
commands, plugins, or permission fragments under the same provider
namespace only when they are genuinely reusable.

## Phase 1: inventory and contract tests

1. Inventory known consumer repos and record for each:
   - deployed skills and commands
   - absolute links
   - `.claude/ai.skillz` submodules
   - OpenCode `skills.paths` entries
   - hybrid skill state that must survive migration
2. Define a small deployment manifest in `ai.skillz` describing each
   skill's shape: generic directory, hybrid files/resources, or
   template-only.
3. Add fixture-based tests that create temporary target repos and
   assert exact links, config files, ignores, and status output.
4. Cover both local-anchor and submodule-anchor modes before changing
   the default deployment path.

Known initial consumers to inspect include `lns`, `tractor`, `piker`,
`modden`, `ai.reply`, and `ai.skillz` itself.

## Phase 2: refactor `scripts/deploy.sh`

1. Introduce explicit concepts for:
   - source anchor (`.ai/ai.skillz`)
   - provider (`claude`, `opencode`, or `all`)
   - anchor method (`symlink` or `submodule`)
   - skill deployment shape
2. Extend the CLI without breaking current consumers during migration:

   ```text
   deploy.sh init <repo> [--method symlink|submodule]
   deploy.sh <skill> <repo> [--provider claude|opencode|all]
   deploy.sh command <name> <repo> [--provider claude|opencode]
   deploy.sh update <repo> [--ref REF]
   deploy.sh status <repo> [--provider all]
   deploy.sh migrate <repo> [--dry-run]
   ```

3. Make all generated provider links relative to `.ai/ai.skillz`.
4. In local mode, add only the anchor path to `.gitignore`; never add
   an absolute link to the index.
5. In submodule mode, initialize and update `.ai/ai.skillz` and stage
   only the gitlink when the user explicitly requests staging.
6. Preserve current hybrid directories and state files in place.
7. Make `status` report:
   - anchor mode and health
   - enabled providers
   - relative, absolute, or broken links
   - unportable `skills.paths` entries
   - legacy `.claude/ai.skillz` deployments
8. Make `migrate --dry-run` print every proposed filesystem and config
   change without changing the target.

The old `.claude/ai.skillz` layout has real external consumers, so it
needs a bounded compatibility period. Keep detection and update support
until all inventoried repos migrate, but emit a clear legacy warning and
do not create new deployments there.

## Phase 3: OpenCode deployment

1. Deploy skills into `.opencode/skills/` using the same manifest as
   Claude deployment.
2. Deploy reusable command shims from `providers/opencode/commands/`
   into `.opencode/commands/`.
3. Avoid editing `opencode.json` when default discovery paths suffice.
4. If a future asset genuinely requires config mutation, add a
   separate config-merge tool with schema validation and explicit
   refusal for unsupported JSONC constructs. Do not splice JSON with
   shell text operations.
5. Validate each fixture with:

   ```text
   opencode debug config
   opencode debug skill
   ```

6. Verify command registration and canonical skill location in the
   resolved OpenCode output.

## Phase 4: documentation and validation

1. Rewrite the root deployment overview around provider-neutral source
   plus provider adapters.
2. Update active `skills/*/DEPLOY.md` files with:
   - OpenCode and Claude destinations
   - local and portable anchor modes
   - exact tracked versus ignored artifacts
   - migration instructions from absolute paths
3. Update `commands/README.md` and script help text for provider-aware
   command deployment.
4. Extend validation to reject or warn on:
   - absolute links in portable fixtures
   - absolute `skills.paths` in committed examples
   - provider command shims with no canonical skill
   - broken hybrid resource links
   - runtime state accidentally staged
5. Keep historical plans unchanged; only active deployment docs become
   normative.

## Phase 5: consumer migration

Migrate one repo at a time in separate commits. For each target:

1. Record the pre-migration status and deployed skill state.
2. Run `deploy.sh migrate <repo> --dry-run` and review its output.
3. Create `.ai/ai.skillz` using the chosen anchor mode.
4. Replace absolute provider links with relative links through the
   anchor.
5. Remove absolute OpenCode `skills.paths` entries after
   `.opencode/skills/` discovery is verified.
6. Preserve `conf.toml`, message archives, style guides, review
   context, and other local state byte-for-byte.
7. Run provider debug commands and skill-specific smoke checks.
8. Commit only that target's deployment migration.

For `lns` specifically:

- retain the current absolute OpenCode path until this phase
- preserve `.claude/skills/commit-msg/conf.toml` and `msgs/`
- replace the absolute `SKILL.md` link
- deploy `.opencode/skills/commit-msg/SKILL.md`
- keep `.opencode/commands/commit-msg.md`
- remove only the `skills.paths` entry from
  `.opencode/opencode.json`, preserving instructions and permissions

## Persisted-state follow-up

After source deployment is stable, separately design a provider-neutral
runtime-state root such as `.ai/state/<skill>/`. That migration must
account for persisted data and shipped behavior:

- existing `.claude/skills/*/msgs/` archives
- `conf.toml` session identifiers
- `review_context.md` and regression context
- latest-message convenience files
- worktree-local state semantics
- external scripts that already reference `.claude/`

Do not combine this state migration with the source-anchor rollout.
It requires fallback reads, explicit migration tooling, and a defined
compatibility window.

## Verification matrix

Exercise at least these cases in temporary repositories:

1. Fresh local anchor with Claude only.
2. Fresh local anchor with OpenCode only.
3. Fresh local anchor with both providers.
4. Fresh submodule anchor with both providers.
5. Existing hybrid `commit-msg` state and archives.
6. Existing `.claude/ai.skillz` submodule migration.
7. Existing absolute OpenCode `skills.paths` migration.
8. Existing unrelated `opencode.json` fields and permissions.
9. Broken anchor and broken provider links.
10. Dirty target worktree with unrelated staged and unstaged files.

Required checks:

```text
bash -n scripts/deploy.sh
bash scripts/validate-skills.sh
deploy.sh status <fixture>
opencode debug config
opencode debug skill
git diff --check
```

The fixture tests must also assert that deploy and migration operations
never stage, unstage, revert, or overwrite unrelated target changes.

## Acceptance criteria

- No committed deployment artifact contains a developer home path.
- OpenCode loads deployed skills without an absolute `skills.paths`.
- Claude Code and OpenCode resolve the same canonical `SKILL.md`.
- Local and submodule anchors produce identical provider link layouts.
- Existing hybrid skill state survives migration unchanged.
- `status` identifies legacy, local-only, portable, and broken states.
- `migrate --dry-run` is complete enough to review before mutation.
- All known consumer repos have an explicit migration result.
- Active deployment docs describe the new layout consistently.

## Rollback

Until every consumer migrates, rollback consists of restoring the prior
provider links and OpenCode `skills.paths` entry while leaving persisted
state untouched. The source anchor can then be removed independently.
Do not delete the legacy compatibility code until the consumer inventory
shows no remaining `.claude/ai.skillz` deployments.
