---
description: Review Python-focused code changes without modifying them.
---

Load the `code-review` skill and follow it completely. Keep the review
read-only and present actionable findings first. Export a JSON report only
when the user explicitly requests it. Publish only after the skill's separate
human-verification gate, preferring its first-class `gish` transport; never
treat this initial command invocation as publication approval.

Review target and context from the user: $ARGUMENTS
