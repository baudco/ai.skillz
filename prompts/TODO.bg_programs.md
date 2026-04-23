Rule to codify (behavioral, not repo)

 Whenever I launch a background process, unconditionally
 report:

 1. The output file path (absolute, copy-pastable).
 2. A concrete tail/watch command (tail -f <path> or
 similar) the user can run in another terminal.
 3. How to kill the task (pkill -f <pattern> or
 equivalent).
 4. What progress signal to expect (per-iteration
 summary line, periodic heartbeat, etc.) so silence
 vs. hang is distinguishable.

 I'll save this as a feedback memory at
 /home/goodboy/.claude/projects/-home-goodboy-repos-tractor/memory/feedback_bg_monitoring.md
 and add an index entry in MEMORY.md once plan mode
 exits.

 Longer-term: modden-managed auto-observation

 User flagged a future direction (not for this cycle):
 when a background task is spawned, the tractor/modden
 integration could auto-attach the task to a terminal
 in the current modden workspace so the user sees
 live output without needing a separate tail -f —
 essentially making the "monitoring path" a
 first-class workspace-managed artifact rather than a
 stray /tmp file the user has to shell into.

 Not actionable now (no modden integration surface
 in tractor yet), but worth recording as a direction
 the bg-monitoring feedback memory should mention so
 it stays paired with the immediate rule. Save as a
 project memory (future direction) alongside the
 feedback (current rule).
