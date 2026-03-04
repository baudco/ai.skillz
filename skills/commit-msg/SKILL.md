---
name: commit-msg
description: >
  Generate piker-style git commit messages from
  staged changes or prompt input, following the
  style guide learned from 500 repo commits.
argument-hint: "[optional-scope-or-description]"
disable-model-invocation: true
allowed-tools: Bash(git *), Read, Grep, Glob, Write
---

## Current staged changes
!`git diff --staged --stat`

## Recent commit style reference
!`git log --oneline -10`

# Piker Git Commit Message Generator

Generate a commit message from the staged diff above
following the piker project's conventions (learned from
analyzing 500 repo commits).

If `$ARGUMENTS` is provided, use it as scope or
description context for the commit message.

For the full style guide with verb frequencies,
section markers, abbreviations, piker-specific terms,
and examples, see
[style-guide-reference.md](./style-guide-reference.md).

## Quick Reference

- **Subject**: ~50 chars, present tense verb, use
  backticks for code refs
- **Body**: only for complex/multi-file changes,
  67 char line max
- **Section markers**: Also, / Deats, / Other,
- **Bullets**: use `-` style
- **Tone**: technical but casual (piker style)

## Claude-code Footer

When the written **patch** was assisted by
claude-code, include:

```
(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

When only the **commit msg** was written by
claude-code (human wrote the patch), use:
```
(this commit msg was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

## Output Instructions

When generating a commit message:

1. Analyze the staged diff (injected above via
   dynamic context) to understand all changes.
2. If `$ARGUMENTS` provides a scope (e.g.,
   `.ib.feed`) or description, incorporate it into
   the subject line.
3. Write the subject line following verb + backtick
   conventions from the
   [style guide](./style-guide-reference.md).
4. Add body only for multi-file or complex changes.
5. Write the message to a file in the repo's
   `.claude/` subdir with filename format:
   `<timestamp>_<first-7-chars-of-last-commit-hash>_commit_msg.md`
   where `<timestamp>` is from `date --iso-8601=seconds`.
   Also write a copy to
   `.claude/git_commit_msg_LATEST.md`
   (overwrite if exists).

---

**Analysis date:** 2026-01-27
**Commits analyzed:** 500 from piker repository
**Maintained by:** Tyler Goodlet
