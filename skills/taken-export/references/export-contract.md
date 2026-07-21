# Taken Export Contract V1

An export consists of an Org fragment and a JSON manifest with the same
basename. The Org file is optimized for human review and insertion. The
manifest carries source identity, target intent, deduplication evidence,
and stale-write guards.

## Copy/Paste Handoffs

A copy/paste handoff uses the same Org rendering invariants but is not an
artifact export. It returns one fenced Org fragment in chat and creates no
manifest, path, content hash, or apply receipt. The fragment contains only
children of the resolved target at the correct headline depth.

Copy/paste is the default mode. When the corpus and target resolve uniquely,
the exporter asks whether to auto-update `current.org` with that exact
fragment. An affirmative answer authorizes Apply only for the named corpus,
target, and unchanged fragment. A copy/paste answer or later human insertion
is not Apply mode: the agent neither edits the corpus nor infers acceptance.

## Paths

Default worktree-local location:

```text
.ai/taken/exports/<export-id>.org
.ai/taken/exports/<export-id>.json
```

Repositories may configure another location. Producers must report the
actual paths and must not stage or ignore them implicitly.

## Org Fragment

The Org file contains only children intended for the manifest's target
headline. It does not repeat the target itself.

Given target `modden/PR LANDING` at level 2:

```org
*** TODO example_branch
:PROPERTIES:
:CREATED: [2026-07-21]
:CARRIED: 0
:REPO: modden/
:PR: https://forge.example/goodboy/modden/pulls/99
:END:
- [ ] review, and land
- [ ] follow-ups,
  * [ ] https://forge.example/goodboy/modden/issues/100
```

Required task properties:

- `CREATED`: bracketed ISO date.
- `CARRIED`: `0` for new proposals.
- `REPO`: repository alias or path when repository work is involved.

Optional established properties:

- `WKS`: logical workspace.
- `PR`: canonical pull-request URL.
- `ISSUE`: canonical issue URL.
- `REVIEW`: canonical review URL.
- `AI_DIALOG` or `AI_SESSION`: only when the human wants a durable resume
  hint and the target corpus already uses that convention.

The Org fragment must not contain export-envelope metadata, content
hashes, worker state, or forge response payloads.

## Manifest

```json
{
  "schema": "taken-export/v1",
  "export_id": "20260721T042225Z_modden_pr-followups",
  "generated_at": "2026-07-21T04:22:25Z",
  "mode": "export",
  "source": {
    "repo": "modden",
    "root": "/home/goodboy/repos/modden",
    "remote": "ssh://git@forge.example/goodboy/modden.git",
    "worktree": "/home/goodboy/repos/modden",
    "branch": "main",
    "head": "0123456789abcdef0123456789abcdef01234567",
    "dirty": true
  },
  "target": {
    "corpus": "/home/goodboy/repos/lns/taken/current.org",
    "ref": "modden/PR LANDING",
    "path": ["modden", "PR LANDING"],
    "id": null,
    "level": 2,
    "expected_sha256": "<sha256>",
    "insertion": "children"
  },
  "org": {
    "path": ".ai/taken/exports/20260721T042225Z_modden_pr-followups.org",
    "sha256": "<sha256>",
    "headline_count": 1,
    "checkbox_count": 2
  },
  "items": [
    {
      "key": "gitea:goodboy/modden:pr:99:followups",
      "title": "example_branch",
      "source_refs": [
        "https://forge.example/goodboy/modden/pulls/99"
      ],
      "canonical_refs": [
        "https://forge.example/goodboy/modden/issues/100"
      ],
      "dedupe": "linked-canonical-issue"
    }
  ],
  "authority": {
    "current_org_write": false,
    "task_state_change": false,
    "commit": false,
    "push": false,
    "forge_write": false
  }
}
```

## Field Rules

- `schema` is exactly `taken-export/v1`.
- `mode` is exactly `export`. Copy/paste mode writes no artifact. Apply
  mode consumes an immutable export and does not rewrite it.
- `source.head` uses the full object ID when available.
- `source.dirty` records observation only; exporters never clean source
  state.
- `target.path` is the required ordered array of exact headline titles.
- `target.ref` is the slash-joined display form of `target.path`; importers
  use `target.path` when title text contains `/`.
- `target.level` equals the number of components in `target.path`.
- `target.corpus` identifies the canonical apply destination. Apply stops if
  the requested destination resolves to a different path.
- `target.id` is preferred when the target has an Org `ID`.
- `target.expected_sha256` is recorded whenever the target is available.
  Apply requires a non-null value and an exact fresh match, regardless of
  whether a human or agent performs the insertion.
- `org.sha256` covers the exact Org fragment bytes.
- `org.headline_count` counts exported task headlines; `org.checkbox_count`
  counts every checkbox item in the fragment at all supported depths.
- `items[].key` should be stable across repeated extraction from the same
  source section.
- `canonical_refs` list trackers linked instead of duplicated.
- Every authority flag is `false` in a V1 export. Apply authorization is
  conveyed by the fresh human request, never by mutating this manifest.

Absolute paths are acceptable in a local handoff manifest but should not
be copied into the Org fragment or committed as portable configuration.

Direct same-session apply may skip artifact creation. It still records a
fresh target hash in working context and verifies that hash immediately
before mutation. This exception does not permit applying an artifact with a
null or stale `target.expected_sha256`.

## Idempotency And Staleness

An importer should reject or pause when:

- the target snapshot hash differs;
- the target path or `ID` is missing or ambiguous;
- an item key already exists in prior import records;
- the target already contains the same PR/issue URL or equivalent task;
- the Org fragment hash does not match the manifest.

Retries must not duplicate headlines or checkboxes. A stale export is a
request for reconciliation, not permission to overwrite newer human
edits.

## Org Rendering Invariants

- Structural list depth is zero-based and limited to `0..2`.
- Bullets alternate by depth: `-`, `*`, `-`.
- The rule applies to checkbox and plain list items, not continuation prose.
- A fourth list level is represented as a child task headline instead.
- Each task has one property drawer with `CREATED`, `CARRIED`, and `REPO`
  when repository work is involved.
- `PR`, `ISSUE`, and `REVIEW` each contain at most one primary URL.

## Future Compatibility

The planned durable reference grammar is:

```text
<hl1>/<hl2>/.../<hlN>::<subtask0>.<subtask1>
id:<org-id>::@<checkbox-anchor>
```

V1 manifests use headline paths and optional Org IDs. Positional
checkbox paths are suitable for display but not unattended writes.
