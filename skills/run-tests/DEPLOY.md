# Deploying `/run-tests`

`run-tests` uses a shared base plus a repository-owned harness reference:

```text
.claude/skills/run-tests/
  SKILL.md -> canonical ai.skillz base
  test-harness-reference.md
```

The base owns execution safety and diagnostics. The local reference owns
commands, environments, paths, backend matrices, fixtures, mappings, and
known outcomes.

## Deployment Script

Deploy an absolute development link:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh \
  run-tests /path/to/repo --method symlink
```

Deploy from a repository's `.claude/ai.skillz` submodule:

```sh
bash /path/to/ai.skillz/scripts/deploy.sh init /path/to/repo
bash /path/to/ai.skillz/scripts/deploy.sh \
  run-tests /path/to/repo --method submodule
```

The script links only `SKILL.md`. It preserves an existing
`test-harness-reference.md` and never creates an unresolved override
implicitly.

## Bootstrap The Local Reference

Copy the override template:

```sh
cp /path/to/ai.skillz/templates/run-tests/SKILL.md.j2 \
  .claude/skills/run-tests/test-harness-reference.md
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

See `references/tractor-example.md` and `references/modden-example.md` for
complete examples with different harnesses.

## Migration Safety

### Existing local `SKILL.md`

The deploy script refuses to overwrite a regular local `SKILL.md`. Extract
its project-specific commands and mappings into
`test-harness-reference.md`, remove or archive the old base, then deploy
again.

### Existing whole-directory symlink

Older consumers may link `.claude/skills/run-tests` to another repository's
entire skill directory. The deploy script unlinks only that directory
symlink, creates a local directory, and installs the canonical `SKILL.md`
link. It never writes through the old link.

### Existing local reference

Repeated deployment preserves the reference byte-for-byte and refreshes only
the canonical `SKILL.md` link.

## OpenCode

OpenCode needs both skill discovery and a slash-command shim. After the
Claude-compatible hybrid layout exists, link that local directory:

```sh
mkdir -p .opencode/skills .opencode/commands
ln -s ../../.claude/skills/run-tests \
  .opencode/skills/run-tests
cp /path/to/ai.skillz/.opencode/commands/run-tests.md \
  .opencode/commands/run-tests.md
```

Track the command shim in consumer repositories. Restart OpenCode after
deployment; skills and commands are loaded at startup.

## Tracking And Ignore Rules

For absolute development deployment:

- the deploy script ignores the absolute
  `.claude/skills/run-tests/SKILL.md` link;
- track `test-harness-reference.md`;
- decide locally whether the OpenCode link is machine-local.

For submodule deployment:

- track the relative `SKILL.md` link;
- track `test-harness-reference.md`;
- track a relative OpenCode skill link and command shim when used.

Do not add command shims to `.gitignore`; they are portable repository
configuration. Deployment links are intentionally absent from the static
`gitignore-patterns.conf` because absolute links should be ignored while
relative submodule links should be tracked.

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
