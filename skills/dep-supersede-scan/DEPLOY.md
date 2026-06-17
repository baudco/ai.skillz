# Deploying `/dep-supersede-scan`

This skill is fully generic — no per-repo customization
needed. It reads the branch diff + queries the repo's
GitHub dependabot API.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/dep-supersede-scan \
      .claude/skills/dep-supersede-scan
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh dep-supersede-scan <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy.sh dep-supersede-scan <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/dep-supersede-scan` → relative symlink
  to `../ai.skillz/skills/dep-supersede-scan`

## Prerequisites

- `gh` CLI authenticated with `security_events` read
  scope (for the dependabot alerts API). Without it the
  alert pass is skipped (reported, not silent); the
  bot-PR pass still works.
- `git` CLI.
- Optional: `python` with `packaging` for PEP-440 version
  comparison (falls back to manual review when absent).

## Pairs with

- `/pr-msg` — findings feed its "Related issues & PRs" /
  Links pass.
