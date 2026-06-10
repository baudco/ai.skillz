---
description: Fork THIS session into a new terminal window
argument-hint: "[optional window title]"
---

Fork the current Claude Code session into a new terminal so I can keep
both running.

Do this by running the following **via the Bash tool** (NOT as a
slash-command `!`-exec — the static analyzer blocks process spawners
like `setsid`):

```bash
setsid -f "${TERMINAL:-alacritty}" -e \
  claude --resume "$(cat .claude/.current_session 2>/dev/null)" \
  --fork-session
```

Notes:
- `.claude/.current_session` holds THIS session's id, stashed by the
  `SessionStart` hook (see `DEPLOY.md` / `session-stash.hook.json`).
  If that file is missing/empty, run the same line but with
  `--continue` instead of `--resume "..."` (forks the most-recent
  session in cwd).
- `$ARGUMENTS` (`{{ARGS}}`) — if given, use it as the new window's
  `--title` (alacritty: add `--title <ARGS>` before `-e`).
- The spawn is detached (`setsid -f`); it returns immediately. Just
  confirm the fork launched in one line — do NOT summarize output or
  take further action.

> The Bash tool will likely prompt you to approve the `setsid` spawn
> (it can't be statically allow-listed). Approve it. For a
> zero-friction, modden-aware path see `DEPLOY.md` (input-box `!` form
> / the optional `branch-in-term.xsh` alias).
