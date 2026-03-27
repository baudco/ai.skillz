# Deploying `/yt-url-lookup`

This skill is fully generic — no per-repo customization
needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/yt-url-lookup \
      .claude/skills/yt-url-lookup
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh yt-url-lookup <your-repo>
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh yt-url-lookup <your-repo>
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/yt-url-lookup` → relative symlink
  to `../ai.skillz/skills/yt-url-lookup`

## Prerequisites

- `yt-dlp` CLI
- Optional: `python3` (for confidence scoring)
