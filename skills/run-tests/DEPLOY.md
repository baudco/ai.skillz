# Deploying `/run-tests`

Configuration and runtime paths follow the
[shared runtime contract](../../docs/runtime-state.md).
Use `--harness agents` for whole-directory shared
discovery; legacy harness deployments below retain hybrid layouts.


`run-tests` uses a shared base plus a repository-owned harness reference:

```text
.agents/skills/run-tests -> canonical ai.skillz base
.ai/run-tests/test-harness-reference.md
```

The base owns execution safety and diagnostics. The local reference owns
commands, environments, paths, backend matrices, fixtures, mappings, and
known outcomes.

## Deployment Script

Deploy ignored absolute development links:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh \
  run-tests /path/to/repo --provider all --method symlink
```

Deploy from a repository's `.ai/ai.skillz` submodule:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh init /path/to/repo
bash /path/to/ai.skillz/scripts/deploy.sh \
  run-tests /path/to/repo --provider all --method submodule
```

Legacy deployment links only `SKILL.md`; shared deployment links
the canonical skill directory. It preserves an existing
`test-harness-reference.md` and never creates an unresolved override
implicitly.

## Bootstrap The Local Reference

Run `runtime prepare <repo>` and use its `test_harness` path. For a
fresh or migrated repository, copy the override template:

```sh
mkdir -p .ai/run-tests
cp /path/to/ai.skillz/templates/run-tests/SKILL.md.j2 \
  .ai/run-tests/test-harness-reference.md
```

Replace every `{{ ... }}` marker before invoking `/run-tests`. The canonical
base rejects an override that still contains Jinja markers.

Template fields:

- `project_name`, `import_name`, `test_root`, `venv_name`
- `environment_setup`, `base_test_command`
- `import_check_command`, `collection_check_command`
- `default_flags`, `custom_flags`
- `fixture_invariants`, `test_layout`, `change_test_mapping`
- `quick_check_commands`, `known_outcomes`, `tractor_runtime_notes`
- `safe_regression_commands`, `authorization_required_commands`
- `process_isolation`

See `references/tractor-example.md` and `references/modden-example.md` for
complete examples with different harnesses.

## Migration Safety

### Existing local `SKILL.md`

The deploy script refuses to overwrite a regular local `SKILL.md`. Extract
its project-specific commands and mappings into
`test-harness-reference.md`, remove or archive the old base, then deploy
again.

### Existing whole-directory symlink

The deploy script can replace a whole-directory link only when it resolves to
a recognized `ai.skillz/skills/run-tests` source. Links to another consumer's
local Run skill are refused because they may be user-owned. Inspect those
links, extract repository-specific guidance into
`test-harness-reference.md`, and unlink them manually before deployment. The
script never writes through the old link.

### Existing local reference

Repeated deployment preserves the reference byte-for-byte and refreshes only
the canonical `SKILL.md` link.

## OpenCode

OpenCode skill deployment installs both skill discovery and its dependent
slash-command shim:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh \
  run-tests /path/to/repo --provider opencode --method symlink
```

All harnesses use the same resolved repository-owned reference.
Legacy references remain supported until explicit runtime migration.
A reference alone does not enable a harness's skill discovery.

Use `--method submodule` after portable initialization.
The canonical shim is tracked at `providers/opencode/commands/run-tests.md`.
Restart OpenCode after deployment; skills and commands are loaded at startup.

## Tracking And Ignore Rules

For absolute development deployment:

- the deploy script ignores the absolute
  `.claude/skills/run-tests/SKILL.md` link;
- track `test-harness-reference.md`;
- ignore absolute OpenCode skill and command links.

For submodule deployment:

- track the relative `SKILL.md` link;
- track `test-harness-reference.md`;
- track relative OpenCode skill and command links when used.

The canonical command source remains tracked in `ai.skillz`. Consumer command
links are local by default; portable relative links are an explicit opt-in.

## Fallback Without An Override

The canonical base can inspect project metadata and run conservative,
evidence-backed commands without a local reference. It reports that fallback
and never imports another repository's package names, flags, mappings, or
known failures.

## Worktrees

An absolute link may need deployment in each worktree. A tracked relative
submodule link is portable when the submodule is initialized there. In every
case, the base resolves `test-harness-reference.md` from the active worktree's
repository root.
