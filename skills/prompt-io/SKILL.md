---
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
disable-model-invocation: false
allowed-tools:
  - Bash(git *)
  - Bash(date *)
  - Bash(mkdir *)
  - Read
  - Grep
  - Glob
  - Write
---

When tracking AI prompt I/O, always follow this
process:

0. **Detect working context**

   Run `git rev-parse --show-toplevel` for the repo
   root and `git rev-parse --git-common-dir` to
   check for worktree context. If the common-dir
   differs from the git-dir, you are in a worktree.
   Tell the user which tree you're operating on.

   Determine `<ai-service>` from the active agent
   (e.g. `claude` for Claude Code, `copilot` for
   GitHub Copilot).

   ```bash
   mkdir -p ai/prompt-io/<ai-service>/
   ```

1. **Classify scope and substantive threshold**

   Evaluate what the AI interaction produced:

   | Scope     | Substantive? | Action         |
   |-----------|-------------|----------------|
   | `code`    | yes         | full log + raw |
   | `config`  | yes         | full log + raw |
   | `data`    | yes         | full log + raw |
   | `docs`    | maybe       | ask human      |
   | `tests`   | maybe       | ask human      |
   | `chat`    | no          | skip           |

   When the scope is ambiguous (`docs`, `tests`),
   ask the human via `AskUserQuestion`:

   ```
   This interaction generated [docs/test] changes.
   Capture a prompt-io log entry?
   (NLNet requires per-commit logging for code;
   docs/tests need only a general README entry.)
   ```

   **Never silently skip when uncertain** — always
   ask the human.

2. **Capture the prompt**

   Record the human's prompt/instruction that drove
   the AI output. Include:
   - The direct user instruction or question
   - Any follow-up clarifications
   - Relevant context provided (file paths, error
     msgs, etc.)

   If the interaction spans multiple turns,
   summarize the prompting sequence with key
   decision points.

3. **Write unedited AI output**

   Generate the timestamp and hash:

   ```bash
   TS=$(date -u +%Y%m%dT%H%M%SZ)
   HASH=$(git log -1 --format=%h)
   ```

   Write the raw AI response to:
   `ai/prompt-io/<service>/<ts>_<hash>_prompt_io.raw.md`

   **This file MUST be written BEFORE any human
   edits are applied to the AI output.**

   Format:

   ```markdown
   ---
   model: <model-name-and-version>
   service: <ai-service>
   timestamp: <ISO-8601>
   git_ref: <short-hash>
   ---

   <verbatim AI output, unedited>
   ```

   If the output exceeds 500 lines, include the
   first 100 lines verbatim plus:
   `[truncated — see git diff for full changes]`

4. **Write the prompt-io log entry**

   Write the main log to:
   `ai/prompt-io/<service>/<ts>_<hash>_prompt_io.md`

   Format:

   ```markdown
   ---
   model: <model-name-and-version>
   service: <ai-service>
   session: <session-uuid>
   timestamp: <ISO-8601>
   git_ref: <short-hash>
   scope: <code|docs|tests|config|data>
   substantive: <true|false>
   raw_file: <ts>_<hash>_prompt_io.raw.md
   ---

   ## Prompt

   <The human's instruction/question that
   initiated this interaction.>

   ## Response summary

   <Concise summary of what the AI generated,
   focusing on the "what" and "why" of changes.>

   ## Files changed

   - `path/to/file1.py` — <brief description>
   - `path/to/file2.py` — <brief description>

   ## Human edits

   <If the human modified the AI output before
   committing, describe the nature of edits here.
   If no edits: "None — committed as generated.">
   ```

5. **Ensure per-service README exists**

   Check for `ai/prompt-io/<service>/README.md`.
   If absent, create it (never overwrite existing):

   ```markdown
   # AI Prompt I/O Log — <service>

   This directory tracks prompt inputs and model
   outputs for AI-assisted development using
   `<service>`.

   ## Policy

   Prompt logging follows the
   [NLNet generative AI policy][nlnet-ai].
   All substantive AI contributions are logged
   with:
   - Model name and version
   - Timestamps
   - The prompts that produced the output
   - Unedited model output (`.raw.md` files)

   [nlnet-ai]: https://nlnet.nl/foundation/policies/generativeAI/

   ## Usage

   Entries are created by the `/prompt-io` skill
   or automatically via `/commit-msg` integration.

   Human contributors remain accountable for all
   code decisions. AI-generated content is never
   presented as human-authored work.
   ```

6. **Emit commit trailer**

   When invoked as part of a `/commit-msg` workflow
   (or when the user is about to commit), suggest
   adding a trailer to the commit message:

   ```
   Prompt-IO: ai/prompt-io/<service>/<filename>.md
   ```

   This links the commit to its prompt provenance
   log.

7. **Present summary**

   Tell the user:
   - Which files were written (log + raw)
   - The prompt-io entry path for reference
   - Reminder that `.raw.md` contains unedited
     output
   - If first entry, note the README creation

## NLNet policy compliance

This skill satisfies five NLNet requirements:

1. **Prompt provenance** — model name, timestamps,
   prompts, and unedited outputs in `.raw.md`
2. **Substantive-use marking** — scope classification
   and `substantive:` frontmatter flag
3. **Quality maintenance** — human accountability
   via `## Human edits` section
4. **No false attribution** — clear separation of
   AI output vs human contribution
5. **Persistent storage** — all logs in-repo under
   git, no third-party login-required platforms

## File naming convention

```
ai/prompt-io/<service>/<ts>_<hash>_prompt_io.md
ai/prompt-io/<service>/<ts>_<hash>_prompt_io.raw.md
```

- `<ts>`: `date -u +%Y%m%dT%H%M%SZ`
  (e.g. `20260402T143012Z`)
- `<hash>`: first 7 chars of HEAD
  (`git log -1 --format=%h`)
- Mirrors `commit-msg/msgs/` naming convention
