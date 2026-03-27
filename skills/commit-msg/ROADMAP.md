# `/commit-msg` Roadmap

## `gish` transport integration

Currently the review-context PATCH flow (step 6) calls
`gh api` directly to update GH review reply comments
with commit hashes. When `gish` supports review reply
management, this should migrate to:

```
gish reply <backend> <pr-num> --update <reply-id> \
  --footer "commit: <hash>"
```

This decouples the skill from GitHub-specific API calls
and enables cross-service commit-ref patching (Gitea,
sr.ht, GitLab).

See `gish/ROADMAP.md` Phase 2 for the `gish reply` spec.

## Auto style-guide generation

The `scripts/generate-style-guide.py` script (when
implemented with `jinja2`) will automate style guide
creation from commit history analysis. Future work:

- Auto-detect project conventions without manual config
- Periodic re-analysis to catch style drift
- Integration with CI to warn on style deviations

## Cross-provider compatibility

The `!git diff --staged --stat` dynamic context injection
(from piker's variant) is Claude-Code-specific. Consider
adding an equivalent for other agentic coding tools that
support pre-invocation context gathering.
