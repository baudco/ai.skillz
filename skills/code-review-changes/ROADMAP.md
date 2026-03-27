# `/code-review-changes` Roadmap

## `gish` transport integration

Currently fetches review comments via `gh api` and
posts replies via `gh api`. When `gish` supports
review operations:

### Fetch reviews
```
gish review <backend> <pr-num>
```
Writes to `<backend>/<pr-num>_review.md` locally.

### Post replies
```
gish reply <backend> <pr-num>
```
Reads reply content from local file, posts to remote,
tracks reply IDs for commit-ref patching.

This decouples the skill from `gh api` and enables
cross-service review handling (Gitea, sr.ht, GitLab).

See `gish/ROADMAP.md` Phases 1-2 for the full spec.

## `/run-tests` dependency

Step 5 (mandatory test verification) currently assumes
a `/run-tests` skill is deployed. Should gracefully
degrade when the skill is absent:

- Check if `.claude/skills/run-tests/SKILL.md` exists
- If missing, warn the user and skip (or run a generic
  `pytest` / `make test` fallback)

## Review polling (`gish watch`)

When `gish watch` is implemented, the review workflow
can be automated end-to-end:

1. `gish watch <backend> <pr-num>` polls for new reviews
2. Writes `.claude/review_ready.md` marker on detection
3. Claude-code hook picks up marker and triggers
   `/code-review-changes` automatically
4. Full cycle: push -> review -> fix -> push

See `gish/ROADMAP.md` Phase 2.5 for the watch spec.
