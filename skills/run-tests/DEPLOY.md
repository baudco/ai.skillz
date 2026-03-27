# Deploying `/run-tests`

This skill requires per-project customization —
there is no generic SKILL.md to symlink.

> Neither symlink nor submodule deployment apply here.
> The SKILL.md is always generated locally from a template.

## Quick setup

### 1. Create skill directory

```bash
mkdir -p .claude/skills/run-tests
```

### 2. Generate SKILL.md from template

Use the Jinja2 template at
`ai.skillz/templates/run-tests/SKILL.md.j2` as a
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

See `ai.skillz/skills/run-tests/references/tractor-example.md`
for a complete, production example from the tractor project.

## What stays local (always)

- `SKILL.md` — entirely project-specific

## Prerequisites

- Your project's test runner (e.g. `pytest`)
