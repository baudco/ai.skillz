---
name: taken-export
description: >
  Export repository work as Taken-compatible Org headlines and
  checkbox subtasks for manual review, artifact handoff, or explicitly
  authorized insertion into current.org. Use when a repository
  supervisor is asked for Taken tasks, Org TODOs, follow-up lists, or a
  current.org submission.
compatibility: >
  Requires repository file access. Optional: git for source identity,
  gish or forge CLIs for issue/PR context, and tkn for target linting.
metadata:
  author: goodboy
  version: "0.1"
---

# Taken Export

Turn repository-local findings into a bounded Taken handoff without
claiming human acceptance or making a repository worker the implicit
owner of the Taken corpus.

Read [references/export-contract.md](references/export-contract.md)
before writing artifacts. See
[references/examples.md](references/examples.md) for representative
outputs.

## Non-Negotiable Authority Boundary

Persistent task state belongs to the human.

- Never change an existing Org headline state or checkbox marker unless
  the current prompt requests that exact state change.
- New proposals use `TODO` headlines and unchecked `[ ]` checkboxes.
- Do not infer `WIP`, `WAIT`, `DONE`, `NOPE`, `[x]`, `[X]`, `[-]`, or
  `[~]` from implementation, test, review, merge, or CI status.
- Preview and export modes never modify `current.org`.
- Apply mode requires an explicit request to insert or submit the
  proposed items to a named corpus or file.
- Never run `tkn roll`, `tkn lint --write`, `git commit`, `git push`, or
  a forge mutation as part of export or apply.

If a target repository has a task-state ownership skill or policy, load
and follow it before inspecting or editing its task files.

## Modes

Choose the least-authority mode that satisfies the request.

### Preview

Use when the human asks to "list", "propose", "draft", or "show" Taken
tasks. Return a fenced `org` fragment in chat. Preview never writes an
artifact; if persistence becomes useful or requested, switch to Export mode
and write the complete Org/manifest pair.

### Export

Use when the human asks to "export", "prepare for Taken", "hand off",
or requests machine-readable output. Write an Org fragment and JSON
manifest under the active worktree's configured export directory,
defaulting to:

```text
.ai/taken/exports/
```

Do not stage the artifacts or add ignore rules implicitly.

### Apply

Use only when the human explicitly asks to "apply", "insert", "submit",
or "add" the export to a specific `current.org` corpus. Validate the
fresh target, show or inspect the exact insertion, and preserve all
existing task markers.

Apply may consume an existing export artifact or use a candidate rendered
earlier in the same session. A direct same-session apply does not require
writing an intermediate artifact, but it still requires a fresh target hash
and all validation below.

If the repository supervisor cannot access the target safely, stop
after export and report the artifact paths for the Taken orchestrator.

## Workflow

### 1. Establish Source Context

Determine:

- repository root and canonical repository identity;
- current branch/worktree and `HEAD`, when Git is available;
- relevant PRs, issues, reviews, plans, tests, and local notes;
- the human's requested scope and desired mode;
- the intended Taken target headline or category.

Use repository-relative paths in prose. Keep volatile execution details
in the manifest, not in Org properties.

For a Git repository, record `git status --short`, `HEAD`, and remotes
read-only. A dirty worktree is valid source context; it must be reported,
not cleaned.

### 2. Collect Candidate Work

Extract actionable future work from the requested sources:

- explicit PR or issue follow-up checklists;
- unresolved review findings;
- deferred plan sections;
- manual verification still requested by the human;
- implementation gaps or risks discovered during the current session;
- repository-local tasks the human asks to transfer.

Separate evidence from work. A commit, passing test, merged PR, or review
URL can support a task description but does not make an exported item
complete.

Do not export speculative cleanup merely because it is possible. Every
item needs a source reference or a clear user request.

### 3. Deduplicate And Link

Before copying detailed follow-ups:

1. Search explicit issue/PR links in the source material.
2. Search local issue caches and plans.
3. Use `gish` or a read-only forge client when available.
4. Compare candidate intent, not just title text.

Prefer one concise checkbox linking a canonical issue over copying its
entire checklist. Copy details only when no canonical tracker exists or
when the human asks for a self-contained export.

Record deduplication decisions and all source links in the manifest.
`gish` is an optional source adapter; it does not own Org rendering or
corpus mutation.

### 4. Resolve The Target

Use a full headline path when known:

```text
<hl1>/<hl2>/.../<hlN>
```

The Org fragment contains children of that target, so exported headline
stars begin at `N + 1`.

Examples:

```text
target: modden
fragment starts: ** TODO ...

target: modden/PR LANDING
fragment starts: *** TODO ...
```

Do not use positional checkbox references as durable identities. If the
target has an Org `ID`, record it in the manifest and prefer it during
apply. Always record the path as ordered title components in
`target.path`; `target.ref` is its human-readable slash-joined form. This
avoids ambiguity when a title itself contains `/`. Otherwise record the
normalized full path and a target snapshot hash when the target file is
available.

If the target is unknown, ask one short question. Do not guess a nested
destination for automatic application.

### 5. Render Taken-Compatible Org

Follow these rules:

- New task headlines use `TODO`.
- New checkbox items use `[ ]`.
- Structural list bullets alternate by zero-based depth: root `-`, child
  `*`, grandchild `-`. Apply this to checkbox and plain list items, with
  two-space indentation per level.
- Do not export list content deeper than depth two. Promote a complex
  branch to a task headline instead of creating a fourth list level.
- Wrap prose consistently with the target corpus when available.
- Include a property drawer for each exported task.
- Set `CREATED` to the target corpus's local export date and `CARRIED`
  to `0`. If the target timezone is unknown, use the UTC date and record
  that choice in the manifest.
- Set `REPO` to a resolvable repository alias or path, never a PR or
  issue URL. Reuse the target category's established `REPO` spelling
  when available; otherwise ask or use an explicit checkout path.
- Put forge URLs in `PR`, `ISSUE`, or `REVIEW` as appropriate.
- Use at most one primary URL for each forge property. Put additional
  canonical links in checkbox prose and the manifest.
- Include `WKS` only when the logical workspace is known.
- Omit transient worker phase, retry, lease, heartbeat, and session
  details unless the human explicitly wants a durable dialog hint.
- Do not add `DONE_REF` or `DONE_SRC` to proposed work.

Keep source provenance, dedupe keys, and snapshot metadata in the JSON
manifest instead of inventing Org properties.

### 6. Return Or Write The Export

For preview mode, return:

1. the proposed Org fragment;
2. a short source/deduplication summary;
3. any unresolved target ambiguity.

For export mode:

1. create one `<export-id>.org` fragment;
2. create one matching `<export-id>.json` manifest;
3. compute and record the Org file SHA-256;
4. re-read both files and validate their agreement;
5. report paths and checks not run.

V1 artifact manifests always use `mode: "export"`. Preview writes no
manifest. Apply consumes an immutable export manifest and reports the
result separately; it does not rewrite the source manifest as a receipt.

Use a filesystem-safe export ID:

```text
<UTC timestamp>_<repo>_<short-slug>
```

### 7. Apply Only With Explicit Authorization

Before editing `current.org`:

1. Re-read the target file immediately before mutation.
2. Verify the target `ID` or full ancestor path resolves exactly once.
3. For an artifact apply, verify the exact Org fragment bytes match
   `org.sha256` and the canonical `target.corpus` path is the requested apply
   destination.
4. For an artifact apply, require a non-null `target.expected_sha256` and
   compare it with the fresh target file SHA-256. For direct same-session
   apply, record the hash before rendering and verify it again immediately
   before mutation. Stop on an absent or differing guard and regenerate or
   ask the human.
5. Search the target subtree for matching forge URLs, dedupe keys, and
   semantically equivalent tasks.
6. Present or inspect the exact additions; do not replace the subtree.
7. Insert only approved new headlines and checkbox items.
8. Preserve every existing headline state, checkbox marker, property,
   ordering choice, and unrelated edit.
9. Run non-writing `tkn lint` when available.
10. Run `git diff --check` and report the target diff.

Do not mutate the export manifest during apply. A future receipt format
may record successful insertion; `taken-export/v1` records intent only.

Never map runtime success to task acceptance. Never mark a parent done
because exported children were inserted.

### 8. Report The Handoff

Report:

- mode used;
- source repository, branch/worktree, and `HEAD`;
- target reference;
- exported or inserted item count;
- canonical issues linked instead of duplicated;
- artifact paths and hashes, when written;
- validation commands and results;
- unresolved risks or stale references;
- whether `current.org` was untouched or explicitly modified.

Do not commit, push, roll, or mutate forge state unless the human makes
a separate explicit request granting that authority.
