---
description: Generate or update a pull-request description for the branch.
---

Load the `pr-msg` skill and follow it completely for the current branch. Use
the user's arguments as base-branch or update context. Generate and preserve
the local PR-message artifacts; do not create, update, or publish a remote PR
unless the user separately authorizes that exact action.

Additional context from the user: $ARGUMENTS
