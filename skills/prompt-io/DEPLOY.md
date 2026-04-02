# Deploying `/prompt-io`

This skill is fully generic — no per-repo
customization needed.

## Method A: Absolute symlinks (single machine)

```bash
ln -s /path/to/ai.skillz/skills/prompt-io \
      .claude/skills/prompt-io
mkdir -p ai/prompt-io/claude
```

Or use the deploy script:

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh \
  prompt-io <your-repo>
mkdir -p <your-repo>/ai/prompt-io/claude
```

## Method B: Git submodule (portable, version-pinned)

### One-time setup

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh \
  init <your-repo>
```

### Deploy this skill

```bash
bash /path/to/ai.skillz/scripts/deploy-skill.sh \
  prompt-io <your-repo>
mkdir -p <your-repo>/ai/prompt-io/claude
```

### What gets committed

- `.gitmodules`, `.claude/ai.skillz` (gitlink)
- `.claude/skills/prompt-io` → relative symlink
  to `../ai.skillz/skills/prompt-io`
- `ai/prompt-io/<service>/README.md`
- `ai/prompt-io/<service>/*_prompt_io.md` entries
- `ai/prompt-io/<service>/*_prompt_io.raw.md`
  entries

## NLNet compliance

This skill implements logging required by:
https://nlnet.nl/foundation/policies/generativeAI/

Deploy it in any NLNet-funded project to ensure
prompt provenance tracking.

## Prerequisites

- `git` CLI
- An AI coding agent that supports the
  agentskills.io specification
