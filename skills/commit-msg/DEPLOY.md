# Deploying `/commit-msg`

## Quick setup

### 1. Create skill directory in your repo

```bash
mkdir -p .claude/skills/commit-msg/msgs
```

### 2. Symlink the generic SKILL.md

```bash
ln -s /path/to/ai.skillz/skills/commit-msg/SKILL.md \
      .claude/skills/commit-msg/SKILL.md
```

### 3. Generate a project-specific style guide

Option A: use the `generate-style-guide.py` script
(requires `jinja2`):

```bash
python /path/to/ai.skillz/scripts/generate-style-guide.py \
  --repo . --commits 500 \
  --output .claude/skills/commit-msg/style-guide-reference.md
```

Option B: have `claude` analyze your commit history
and write the style guide manually, using the examples
in `ai.skillz/skills/commit-msg/references/` as models.

### 4. (Optional) Create session tracking config

```bash
cp /path/to/ai.skillz/templates/commit-msg/conf.toml.j2 \
   .claude/skills/commit-msg/conf.toml
```

Edit to uncomment and set a fresh UUID, or let the
skill generate one on first invocation.

## What stays local (per-repo)

- `style-guide-reference.md` — your repo's commit style
- `conf.toml` — session tracking UUID
- `msgs/` — generated commit message archive

## What gets symlinked (from ai.skillz)

- `SKILL.md` — the generic workflow definition

## Prerequisites

- `git` CLI
- Optional: `gh` CLI (for review context integration
  with `/code-review-changes`)
