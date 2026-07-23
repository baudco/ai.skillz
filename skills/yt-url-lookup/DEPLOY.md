# Deploying `/yt-url-lookup`

This is a generic whole-directory skill with no per-repo skill state.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
# or: ... init <repo> --method submodule

bash /path/to/ai.skillz/scripts/deploy.sh yt-url-lookup <repo> \
  --provider <claude|opencode|all>
```

The local method creates an ignored `.ai/ai.skillz` symlink to a local
checkout. The portable method creates a version-pinned submodule there.
Provider links are relative and target the same canonical directory:
`.claude/skills/yt-url-lookup` and
`.opencode/skills/yt-url-lookup`.

Track provider links and, in submodule mode, `.gitmodules` plus the
anchor gitlink. Nothing is staged unless `--stage` is explicitly
supplied. Quit and restart OpenCode after deployment or update. Default
`.opencode/skills/`
discovery requires no `opencode.json` or `opencode.jsonc` mutation.

## Maintenance

```bash
bash /path/to/ai.skillz/scripts/deploy.sh status <repo> --provider all
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo> --dry-run
bash /path/to/ai.skillz/scripts/deploy.sh migrate <repo>
bash /path/to/ai.skillz/scripts/deploy.sh update <repo> [--ref <ref>]
bash /path/to/ai.skillz/scripts/validate-deployment.sh <repo>
```

Preview migration before applying it. Use `update` for a submodule;
update a local source checkout directly.

## Prerequisites

- `yt-dlp` CLI
- Optional: `python3` (for confidence scoring)
