# Deploying `/run-tests`

This skill requires per-project customization. There is no canonical
`skills/run-tests/SKILL.md` to link, so skill deployment is intentionally
template-only.

The local and submodule methods apply only to locating the source
template through the provider-neutral `.ai/ai.skillz` anchor:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or use a portable, version-pinned anchor: --method submodule
```

Do not deploy `run-tests` as a source symlink. Generate a local
`SKILL.md` for each enabled provider destination:

- Claude Code: `.claude/skills/run-tests/SKILL.md`
- OpenCode: `.opencode/skills/run-tests/SKILL.md`

When both providers use the same test workflow, generate once and copy
the resulting project-owned file into both destinations. This is the
template-only equivalent of `--provider claude|opencode|all`; there is
no shared skill link to track.

## Quick setup

### 1. Create skill directory

```bash
mkdir -p .claude/skills/run-tests
# For OpenCode instead or as well:
mkdir -p .opencode/skills/run-tests
```

### 2. Generate SKILL.md from template

Use the Jinja2 template at
`.ai/ai.skillz/templates/run-tests/SKILL.md.j2` as a
starting point.

Fill in these project-specific sections:
- `{{ project_name }}` — your project name
- `{{ test_runner }}` — e.g. `pytest`
- `{{ test_command }}` — e.g. `python -m pytest`
- `{{ test_dir }}` — e.g. `tests/`
- `{{ import_check }}` — import smoke test command
- `{{ test_layout }}` — your test directory tree
- `{{ change_test_mapping }}` — module-to-test mapping
- `{{ known_flaky }}` — known flaky tests
- `{{ custom_flags }}` — project-specific pytest flags

### 3. Reference example

See `.ai/ai.skillz/skills/run-tests/references/tractor-example.md`
for a complete, production example from the tractor project.

## What stays local (always)

- `SKILL.md` — entirely project-specific

Track each generated provider `SKILL.md`; it is project configuration,
not generated runtime state. In submodule mode, also track `.gitmodules`
and the `.ai/ai.skillz` gitlink. In local mode, ignore the absolute
anchor. The deployment tooling stages only when `--stage` is explicitly
supplied.

Quit and restart OpenCode after creating or changing its local
`SKILL.md`. OpenCode discovers `.opencode/skills/` by default, and the
deployment tooling does not mutate `opencode.json` or `opencode.jsonc`.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

`status` identifies template-generated local skills. Migration must not
replace or rewrite them. Updating the anchor updates the source template
only; regenerate local `SKILL.md` files deliberately after reviewing
template changes. Use `update` for submodule anchors and update a local
checkout directly.

## Prerequisites

- Your project's test runner (e.g. `pytest`)
