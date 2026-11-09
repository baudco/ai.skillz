---
description: Fork THIS session (by exact id) into a new terminal window
argument-hint: "[optional note — unused for now]"
allowed-tools: Bash(setsid:*), Bash(cat:*)
---

Forking the current session into a new terminal by its EXACT id — read
from `.claude/.current_session`, which the `SessionStart` hook stashes
(see this command's `DEPLOY.md`). Using the precise id avoids
`--continue` grabbing the wrong "most-recent" session in this cwd.

!`session_id="$(cat .claude/.current_session 2>/dev/null)"; if [ -z "$session_id" ]; then echo "branch-in-new-terminal: no stashed session id; install the SessionStart hook or use the documented fallback" >&2; exit 1; fi; setsid -f "${TERMINAL:-alacritty}" -e claude --resume "$session_id" --fork-session >/dev/null 2>&1 & echo "forked session '$session_id' into new ${TERMINAL:-alacritty}"`

<!--
  PREREQ: a `SessionStart` hook must stash the session id to
  `.claude/.current_session` (see `DEPLOY.md` / `session-stash.hook.json`):

    "SessionStart": [{"matcher": "*", "hooks": [
      {"type": "command",
        "command": "mkdir -p \"$CLAUDE_PROJECT_DIR/.claude\" && stash=\"$CLAUDE_PROJECT_DIR/.claude/.current_session\" && rm -f \"$stash\" && session_id=\"$(jq -er '.session_id | select(type == \"string\" and length > 0)')\" && tmp=\"$(mktemp \"$stash.XXXXXX\")\" && printf '%s\\n' \"$session_id\" > \"$tmp\" && mv \"$tmp\" \"$stash\""}]}]

  FALLBACK (no hook installed) — fork the most-recent session in cwd
  instead; simpler but CAN grab the wrong session if you started
  another here since:

    !`setsid -f "${TERMINAL:-alacritty}" -e claude --continue --fork-session >/dev/null 2>&1 & echo "🌱 forked (most-recent) → new terminal"`

  MODDEN-TERMMAN VARIANT (WIP) — swap the bare `setsid $TERMINAL -e`
  for modden's terminal-manager so the branch terminal is opened +
  placed WM-aware (i3/sway) and titled. Sketch (adjust to the real
  termman CLI/IPC, and add it to `allowed-tools`):

    !`mod term open --title "claude:branch" --cmd "claude --resume \"$(cat .claude/.current_session)\" --fork-session"`

  NOTE on the `-e` exec flag: right for alacritty / xterm / foot;
  gnome-terminal wants `-- ` and kitty takes the command bare. Adjust
  the spawn line (and `allowed-tools`) for your emulator.
-->

(Fork launched in a new terminal — no further action needed; just confirm.)
