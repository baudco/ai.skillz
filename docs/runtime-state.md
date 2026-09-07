# Repository configuration and workflow state

Skill discovery lives in `.agents/skills/` or a harness adapter tree.
Repository configuration lives in `.ai/`; generated workflow artifacts
live in `.ai/state/`. This contract is shared by Codex, Claude Code,
and OpenCode. It does not depend on the model provider.

## Workflow integration

`commit-msg`, `commit-plan`, `pr-msg`, `code-review-changes`, and
`run-tests` share this procedure. Before reading project guidance or
writing state, run:

```sh
python3 <source>/scripts/workflow-state.py prepare <repo-root>
```

`<source>` is the canonical `ai.skillz` checkout containing the loaded
skill (resolve its `SKILL.md` symlink), or the validated `.ai/ai.skillz`
anchor. `<repo-root>` is the active worktree root. A copied skill
without the helper is incomplete; deploy from the full source checkout.

Stop on reported conflicts. The JSON `paths` object supplies paths
relative to that worktree for the entire composed workflow. Substitute
these values for tokens such as `<commit_messages>` in skill examples,
generated commands, and artifacts; never write the tokens literally.
Reuse this resolution across skills rather than selecting independent
locations. Never write consumer state through skill discovery links.

Fresh repositories use `.ai` configuration and `.ai/state` artifacts.
Existing data keeps its legacy backend until explicit migration;
source deployment does not migrate archives. Resolution, migration,
and recovery details follow.

## Resolution

`runtime status` is read-only. `runtime prepare`, used by the skills,
creates ignore rules and `.ai/workflow-state.json` with version 1 and
one `backend`: `legacy` or `neutral`. Track this selection and project
guidance; private `conf.toml` files and generated state remain ignored.
No command stages files or edits Git history.

Without a selection, existing legacy files select `legacy`; a fresh
repository selects `neutral`. Empty directories do not count as data.
Mixed layouts require reconciliation. Neutral guidance is preferred,
but divergent duplicate guidance blocks an unmigrated repository.
The JSON `paths` values are relative to the active worktree root.
Every composed workflow uses these resolved paths, including generated
commit-plan commands and helper files.

| Content | Neutral destination |
| --- | --- |
| Commit style | `.ai/commit-msg/style-guide-reference.md` |
| Test harness reference | `.ai/run-tests/test-harness-reference.md` |
| Private commit configuration | `.ai/commit-msg/conf.toml` |
| Private PR configuration | `.ai/pr-msg/conf.toml` |
| Commit archive | `.ai/state/commit-msg/msgs/` |
| Latest commit message | `.ai/state/commit-msg/LATEST.md` |
| PR archive | `.ai/state/pr-msg/msgs/` |
| Latest PR description | `.ai/state/pr-msg/LATEST.md` |
| Review handoff | `.ai/state/review/context.md` |
| Regression handoff | `.ai/state/review/regression.md` |
| Reply candidates | `.ai/state/review/replies/` |

Legacy sources are the corresponding `.claude/skills/` locations,
`.claude/git_commit_msg_LATEST.md`, `.claude/review_context.md`,
`.claude/review_regression.md`, and `.claude/review_replies/`.
Other root `.claude/git_commit_msg_*.md` files enter the commit archive.
The resolver reports exact legacy and neutral inventories with hashes.

Already neutral `.ai/code-review/reports/`, `.ai/taken/exports/`,
Git worktree coordination, and `wkts/` retain their existing contracts.
Harness-specific session files and discovery adapters stay with their
harness. Historical examples and proposed roadmap paths are not an
instruction to write new runtime state there.

## Porting an existing deployment

Updating linked skills does not move data. Refresh deployment ignore
rules using the repository's existing method and harness selection.
The first workflow invocation also installs the neutral state ignores.
Keep the permanent source checkout as the link target.

Pause workflow writers in the target worktree before migration.
Finish pending commit plans or archive their execution helpers outside
the managed paths, then regenerate any plan that will still be used.
The preview refuses `.patch`, `.py`, `.sh`, and `.xsh` archive helpers;
it cannot determine whether they are still pending. Do not blindly
rewrite patches, cached indexes, or executable plans.

These commands work as individual shell lines, including in xonsh:

```sh
cd /path/to/consumer
bash /path/to/ai.skillz/scripts/deploy.sh runtime status .
bash /path/to/ai.skillz/scripts/deploy.sh runtime migrate .
bash /path/to/ai.skillz/scripts/deploy.sh runtime migrate . --apply <preview-sha256>
```

The second command is a read-only preview. Review its `operations` and
`blockers`, then supply its exact `sha256` to apply. Changed source
content invalidates the preview. Divergent destinations, symlinks,
unsupported file types, ignored project guidance, and extra provider
payloads require manual reconciliation. Additional `.opencode/` or
`.codex/` local payloads are reported, never selected silently.

Apply copies files, preserving legacy originals and message bytes.
Only the active review context has known stored path prefixes changed.
Historical messages and reply candidates remain byte-identical;
regenerate a pending candidate if it embeds an actionable old path.
Identical destinations are accepted; divergent ones are never replaced.
The backend changes only after successful copies and a recovery record
at `.ai/state/migrations/workflow-state.json`. Repeating a successful
migration is harmless. Later changes to legacy originals stop workflow
resolution, exposing writers still using the old contract.

Review and commit the neutral guidance, selection, and ignore changes
separately from ignored runtime data. Tracked legacy guidance is left
in Git untouched: its eventual removal is a separate reviewed change.
Migrate each existing worktree independently. A worktree containing a
tracked neutral selection plus legacy data needs its own reviewed
migration; do not point it at another worktree's runtime directory.

## Recovery and limits

A normal copy failure removes files created by that application and
restores the previous `.gitignore`; empty directories may remain.
Sources and pre-existing destinations are preserved. An interrupted
process can leave partial neutral copies or a `.new` selection file.
Inspect these against the preview before removing only incomplete
outputs and retrying. Never delete the legacy originals automatically.

Once neutral writes have occurred, reverting the backend alone would
lose their visibility. Reconcile those changes with the preserved
legacy copies before an intentional rollback. Keep the recovery record
while originals remain: it distinguishes retained backups from new
legacy writes. Hash checks detect drift but do not lock other agents;
application requires a quiet worktree.

Run a fresh preview before every actual migration. Keep inventories
of local repositories and their usage in ignored local state, such as
`.ai/state/migrations/`, rather than in public documentation.
