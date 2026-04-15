# Deploying `/commit-msg`

## Method A: Absolute symlinks (single machine)

### 1. Create skill directory in your repo

```bash
mkdir -p .claude/skills/commit-msg/msgs
```

### 2. Symlink the generic SKILL.md

```bash
ln -s /path/to/ai.skillz/skills/commit-msg/SKILL.md \
      .claude/skills/commit-msg/SKILL.md
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh commit-msg <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh commit-msg <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/commit-msg/SKILL.md` → relative symlink
  to `../../ai.skillz/skills/commit-msg/SKILL.md`
- per-repo files (`style-guide-reference.md`, etc.)

### What gets gitignored

- `msgs/`, `conf.toml`, `*_LATEST.md`

## Post-deploy setup

### Generate a project-specific style guide

**Option A** (recommended): use the
`generate-style-guide.py` script (no deps beyond
Python stdlib):

```bash
python /path/to/ai.skillz/scripts/generate-style-guide.py \
  . --commits 500 \
  --output .claude/skills/commit-msg/style-guide-reference.md
```

This analyzes the repo's commit history and writes
a complete `style-guide-reference.md` with quantified
patterns (verb frequencies, backtick usage, section
markers, abbreviations, tone indicators, examples).

Optional flags:
- `--author <pattern>` — filter to a specific
  author's commits
- `-n <count>` — number of commits (default: 500)

**Option B**: have `claude` analyze your commit
history and write the style guide manually, using
the examples in
`ai.skillz/skills/commit-msg/references/` as
models. The output should match the same structure
as Option A's generated guide.

### (Optional) Create session tracking config

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
