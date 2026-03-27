# Plan: Dual deployment — submodule + symlink support

## Context

Consumer repos (tractor, piker, modden) currently use
absolute symlinks to `ai.skillz/skills/` — these are
machine-specific and not committable. Adding git submodule
support gives version-pinned, portable deployment alongside
the existing symlink convenience.

---

## Design: two methods, identical result

Both methods produce the same `.claude/skills/<name>/`
structure — the difference is how the link targets resolve.

### Method A: symlink (current, dev-machine-only)

```
.claude/skills/py-codestyle -> /home/goodboy/repos/ai.skillz/skills/py-codestyle  # absolute
.claude/skills/commit-msg/SKILL.md -> /home/goodboy/repos/ai.skillz/skills/commit-msg/SKILL.md
```

### Method B: submodule (portable, committable)

```
.claude/ai.skillz/              # submodule checkout
.claude/skills/py-codestyle -> ../ai.skillz/skills/py-codestyle     # relative
.claude/skills/commit-msg/SKILL.md -> ../../ai.skillz/skills/commit-msg/SKILL.md
```

### Auto-detection

When `--method` is not specified, the script checks:
- `.claude/ai.skillz/` exists and is a git submodule
  → use `submodule` (relative symlinks)
- otherwise → use `symlink` (absolute symlinks)

---

## Step 1: Add `.gitignore` to ai.skillz

```gitignore
__pycache__/
*.pyc
py313/
Session.vim
*.swp
```

## Step 2: Rewrite `scripts/deploy-skill.sh`

### New CLI interface

```
deploy-skill.sh init <target-repo> [--url URL] [--ref REF]
    Add ai.skillz as a git submodule at .claude/ai.skillz/.
    Default URL: file:///home/goodboy/repos/ai.skillz

deploy-skill.sh <skill-name> <target-repo> [--method symlink|submodule]
    Deploy a single skill. Auto-detects method.

deploy-skill.sh update <target-repo> [--ref REF]
    Update submodule to latest or specific ref.

deploy-skill.sh status <target-repo>
    Show deployed skills and their method.
```

### Core logic: relative path computation

```bash
# Directory symlink (from .claude/skills/ level):
#   .claude/skills/<name> -> ../ai.skillz/skills/<name>
rel_dir_link="../ai.skillz/skills/$SKILL_NAME"

# File symlink (from .claude/skills/<name>/ level):
#   .claude/skills/<name>/SKILL.md -> ../../ai.skillz/skills/<name>/SKILL.md
rel_file_link="../../ai.skillz/skills/$SKILL_NAME/SKILL.md"
```

### Per-skill deployment patterns

| Skill | Type | Symlink target |
|-------|------|---------------|
| py-codestyle, gish, code-review-changes, inter-skill-review, resolve-conflicts, yt-url-lookup, plan-io | dir link | `../ai.skillz/skills/<name>` |
| commit-msg | hybrid | SKILL.md: `../../ai.skillz/skills/commit-msg/SKILL.md` |
| pr-msg | hybrid | SKILL.md + references/: `../../ai.skillz/skills/pr-msg/{SKILL.md,references}` |
| run-tests | template | no symlinks (local SKILL.md from template) |

### `init` subcommand

```bash
cd "$TARGET_REPO"
git submodule add "${URL:-file:///home/goodboy/repos/ai.skillz}" .claude/ai.skillz
if [ -n "${REF:-}" ]; then
    git -C .claude/ai.skillz checkout "$REF"
    git add .claude/ai.skillz
fi
mkdir -p .claude/skills
```

### `status` subcommand

Iterates `.claude/skills/`, checks each entry:
- symlink → absolute or relative?
- directory → has symlinked SKILL.md?
- submodule present at `.claude/ai.skillz/`?
- broken symlinks?

## Step 3: Update all DEPLOY.md files

Each DEPLOY.md gets dual instructions:

```markdown
## Method A: Absolute symlinks (single machine)
[existing content]

## Method B: Git submodule (portable, version-pinned)

### One-time setup
    deploy-skill.sh init <your-repo>

### Deploy this skill
    deploy-skill.sh <skill-name> <your-repo>

### What gets committed
- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- relative symlinks in `.claude/skills/`
- per-repo files (style-guide-reference.md, etc.)

### What gets gitignored
- `msgs/`, `conf.toml`, `*_LATEST.md`
```

## Step 4: Test on tractor

```bash
cd ~/repos/tractor
# init submodule with local file:// URL
deploy-skill.sh init . --url file:///home/goodboy/repos/ai.skillz
# deploy skills
deploy-skill.sh py-codestyle .
deploy-skill.sh commit-msg .
deploy-skill.sh code-review-changes .
# verify
deploy-skill.sh status .
ls -la .claude/skills/
readlink .claude/skills/py-codestyle
```

---

## Files to modify

- `scripts/deploy-skill.sh` — full rewrite with subcommands
- `skills/*/DEPLOY.md` — add Method B instructions (all 10)
- `.gitignore` — new file at repo root

## Verification

1. `deploy-skill.sh init ~/repos/tractor --url file://...`
   creates `.gitmodules` and `.claude/ai.skillz/`
2. `deploy-skill.sh py-codestyle ~/repos/tractor` creates
   relative symlink that resolves correctly
3. `deploy-skill.sh commit-msg ~/repos/tractor` creates
   hybrid dir with relative SKILL.md symlink + local files
4. `deploy-skill.sh status ~/repos/tractor` shows all
   deployed skills and their method
5. All symlinks resolve: `cat ~/repos/tractor/.claude/skills/py-codestyle/SKILL.md`
6. `bash scripts/validate-skills.sh` still passes on ai.skillz itself
