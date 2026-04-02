# Plan: Create `/prompt-io` skill

## Context

NLNet's [generative AI policy][nlnet] requires funded
projects to maintain prompt provenance logs — tracking
model name, timestamps, prompts, and unedited outputs
for all substantive AI-generated work. The user wants
a new skill (modeled on `/plan-io`) that automates
this tracking in a `ai/prompt-io/` subdir within any
deployed repo.

[nlnet]: https://nlnet.nl/foundation/policies/generativeAI/

---

## Directory layout

```
ai/
└── prompt-io/
    └── <ai-service>/           # claude, copilot, etc.
        ├── README.md           # NLNet-required usage description
        ├── <ts>_<hash>_prompt_io.md      # log entry
        └── <ts>_<hash>_prompt_io.raw.md  # unedited AI output
```

- `<ts>`: `date -u +%Y%m%dT%H%M%SZ`
- `<hash>`: `git log -1 --format=%h` (7 chars)
- Mirrors `commit-msg/msgs/` naming convention

---

## Files to create

### 1. `skills/prompt-io/SKILL.md`

Frontmatter:
```yaml
name: prompt-io
description: >
  Track AI prompt I/O alongside code changes.
  Implement NLNet generative AI policy for prompt
  provenance, substantive-use marking, and
  attribution transparency.
compatibility: >
  Designed for Claude Code (or similar agentic
  coding tools). Requires git CLI.
metadata:
  author: goodboy
  version: "0.1"
disable-model-invocation: true
allowed-tools:
  - Bash(git *)
  - Bash(date *)
  - Bash(mkdir *)
  - Read
  - Grep
  - Glob
  - Write
```

Step-by-step protocol:

- **Step 0** — detect repo root, worktree context,
  determine `<ai-service>`, `mkdir -p` the target dir
- **Step 1** — classify scope (`code|config|data|
  docs|tests|chat-only`) and determine if
  substantive; ask human when uncertain
- **Step 2** — capture the human prompt(s) that drove
  the AI output (summarize multi-turn into key
  decision points)
- **Step 3** — write `.raw.md` with unedited AI
  output BEFORE any human edits (YAML frontmatter:
  model, service, timestamp, git_ref); truncate at
  100 lines if >500 lines
- **Step 4** — write main `_prompt_io.md` log entry
  with sections: `## Prompt`, `## Response summary`,
  `## Files changed`, `## Human edits`
- **Step 5** — ensure per-service `README.md` exists
  (NLNet broad-disclosure requirement); create once,
  never overwrite
- **Step 6** — emit `Prompt-IO:` commit trailer
  pointing to the log entry path
- **Step 7** — present summary to user

### 2. `skills/prompt-io/DEPLOY.md`

Standard dual-method deploy (symlinks + submodule),
following `plan-io/DEPLOY.md` pattern. Post-deploy:
`mkdir -p ai/prompt-io/claude`.

### 3. `skills/prompt-io/references/nlnet-policy-summary.md`

Condensed reference of NLNet's 5 key areas so the
agent has quick context without web fetching:
1. Prompt provenance log requirements
2. Substantive-use marking
3. Quality maintenance
4. No false attribution
5. Reduced logging for non-code uses

---

## Log entry format

### Main entry (`_prompt_io.md`)

```yaml
---
model: claude-opus-4-6
service: claude-code
session: <uuid>
timestamp: 2026-04-02T14:30:12Z
git_ref: abc1234
scope: code
substantive: true
raw_file: <ts>_<hash>_prompt_io.raw.md
---
```

```markdown
## Prompt
<human instruction/question>

## Response summary
<concise summary of AI output>

## Files changed
- `path/to/file.py` - <brief description>

## Human edits
None — committed as generated.
```

### Raw file (`_prompt_io.raw.md`)

```yaml
---
model: claude-opus-4-6
service: claude-code
timestamp: 2026-04-02T14:30:12Z
git_ref: abc1234
---
```

Followed by verbatim AI output, pre-human-edit.

---

## Substantive threshold

| Scope     | Substantive? | Action           |
|-----------|-------------|------------------|
| `code`    | yes         | full log + raw   |
| `config`  | yes         | full log + raw   |
| `data`    | yes         | full log + raw   |
| `docs`    | maybe       | ask human        |
| `tests`   | maybe       | ask human        |
| `chat`    | no          | skip             |

---

## Integration with existing skills

- **`/commit-msg`**: future addition of `Prompt-IO:`
  trailer + check for missing log entries on
  AI-generated patches (separate commit, deferred)
- **`/plan-io`**: plan summaries can reference
  associated prompt-io entries
- No modifications to existing skills in this PR

---

## Update `README.md`

Add row to skill table:
```
| `prompt-io` | AI prompt I/O provenance logging |
```

---

## Verification

1. Inspect `skills/prompt-io/SKILL.md` frontmatter
   matches agentskills.io spec
2. Verify `DEPLOY.md` follows dual-method pattern
3. Confirm `references/nlnet-policy-summary.md`
   covers all 5 NLNet policy areas
4. Check `README.md` skill table includes new entry
5. Run `/inter-skill-review` to verify cross-skill
   consistency
