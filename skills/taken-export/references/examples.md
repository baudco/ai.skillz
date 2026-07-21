# Taken Export Examples

## Copy/Paste Handoff

Request:

```text
Render copy/paste-ready Taken tasks for the deferred work in this plan
under tractor/subinterpreters.
```

Response:

```org
*** TODO subinterpreter follow-ups
:PROPERTIES:
:CREATED: [2026-07-21]
:CARRIED: 0
:REPO: tractor/
:END:
- [ ] add cancellation coverage for interpreter teardown
- [ ] track upstream `msgspec` subinterpreter support:
  https://github.com/example/msgspec/issues/123
```

The response contains only the fenced Org fragment. It does not write an
artifact, manifest, or target corpus.

When the corpus and target resolve uniquely, follow the block with a
structured question equivalent to:

```text
Auto-update /home/goodboy/repos/lns/taken/current.org under
tractor/subinterpreters with this exact fragment?

Copy/paste only (recommended)
Auto-update current.org
```

Selecting auto-update authorizes only that fragment and destination. The
copy/paste choice ends the handoff without modifying files.

## Forge Follow-Ups With Deduplication

Sources:

- PR body contains ten detailed review findings.
- Existing issue `#58` already tracks those findings.

Prefer:

```org
*** TODO wks_save_round2
:PROPERTIES:
:CREATED: [2026-07-21]
:CARRIED: 0
:REPO: modden/
:PR: https://pikers.dev/goodboy/modden/pulls/57
:END:
- [ ] review, and land
- [ ] inherited repr-scan findings:
  * [ ] https://pikers.dev/goodboy/modden/issues/58
```

Do not copy issue `#58`'s complete checklist into the Org fragment. Put
the PR, review, and canonical issue URLs in the manifest's source and
canonical reference lists.

## Export Artifact

Request:

```text
Export these tasks for automatic handoff to
modden/PR LANDING in ~/repos/lns/taken/current.org.
```

Result:

```text
.ai/taken/exports/20260721T042225Z_modden_pr-landing.org
.ai/taken/exports/20260721T042225Z_modden_pr-landing.json
```

The manifest records `target.path = ["modden", "PR LANDING"]`, display
reference `target.ref = "modden/PR LANDING"`, target level 2, the source
Git identity, Org hash, and `current_org_write = false`.

The Taken orchestrator can inspect and apply this artifact later. Export
completion is evidence, not task acceptance.

## Explicit Apply

Request:

```text
Apply that export to ~/repos/lns/taken/current.org under
modden/PR LANDING. Do not alter any existing task states.
```

The worker must re-read the target, verify its path or Org `ID`, compare
the expected hash, deduplicate again, insert only missing children, run
non-writing `tkn lint`, and show the diff.

If the target changed after export, stop and propose reconciliation.
Never replace the whole target subtree with the exported fragment.
Apply also stops if the export has no target snapshot hash. It never
rewrites the export manifest to record success.

## List Depth

Taken exports use at most three list levels and alternate structural
bullets for checkbox and plain items:

```org
- [ ] root follow-up
  * supporting context
  * [ ] child follow-up
    - [ ] grandchild follow-up
```

If another level seems necessary, export a child `TODO` headline instead.

## Repository And Forge Properties

Correct:

```org
:REPO: modden/
:PR: https://pikers.dev/goodboy/modden/pulls/61
:ISSUE: https://pikers.dev/goodboy/modden/issues/53
```

Incorrect:

```org
:REPO: https://pikers.dev/goodboy/modden/pulls/61
```

`REPO` resolves a checkout. Forge objects use their dedicated fields.
