---
name: gish
description: >
  Read, create, edit, sync, and publish human-approved issue/PR content across
  git service backends (GitHub, Gitea, etc.) using local markdown files.
compatibility: >
  Requires git CLI. Optional: gh CLI for GitHub,
  configured modden-capable xonsh + py-gitea for Gitea.
metadata:
  author: goodboy
  version: "0.2"
argument-hint: "[inspect-pr|read|edit|create|sync|comment-reply|comment-edit|review-post|list] [backend] [target]"
allowed-tools:
  - Bash(gh *)
  - Bash(git *)
  - Bash(python *)
  - Bash(xonsh *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Glob
  - Grep
  - Write
user-invocable: true
---

Manage issues and PRs locally as markdown files with
optional sync to remote git services. The canonical
source for this skill lives in `ai.skillz/skills/gish/`.

See also:
- [references/backends.md](references/backends.md) —
  per-backend capabilities
- [references/format.md](references/format.md) —
  markdown file conventions
- [references/review-publication.md](references/review-publication.md) —
  human-approved top-level review publication contract
- [ROADMAP.md](ROADMAP.md) — cross-service review +
  AI skill convergence plan

## Runtime Selection

The shell running the coding harness and the environment implementing a forge
backend are separate choices. Do not assume bare `xonsh` on `PATH` is the
modden environment, and do not infer backend readiness from `$SHELL`.

For the current Gitea backend, prefer the stable launcher bundled with this
skill:

```text
<gish-skill-dir>/scripts/gish-xontrib --check
<gish-skill-dir>/scripts/gish-xontrib <legacy-xontrib-args...>
```

It reads an absolute xonsh path from
`$XDG_CONFIG_HOME/ai.skillz/gish-xonsh`, or from the process-local
`AI_SKILLZ_GISH_XONSH` override. Configure it only with explicit user
approval; see `DEPLOY.md`. The selected xonsh must load modden's `gish`
xontrib under `--no-rc`, which also proves its Python dependencies are
available.

The launcher currently exposes the modden xontrib's legacy Gitea command
surface. It does not manufacture newer normalized `/gish` operations which
the xontrib has not implemented. For those operations, use a supported direct
provider adapter only when the user prefers and authorizes that fallback, or
stop with the unavailable capability clearly identified.

## Safety Boundary

Reading local files and remote public metadata does not authorize remote
mutation. Creating, editing, syncing, commenting, or publishing requires a
current human message which names the exact target and action. Never infer
remote-write permission from loading this skill, an earlier approval, or a
content-producing skill's initial invocation.

Network access is also explicit. A direct current-prompt `/gish inspect-pr`
or `/gish read` request authorizes the metadata read named by that invocation.
A parent skill's desire for fresh data, including review or PR-message
generation, does not self-authorize network access.

## Invocations

- `/gish inspect-pr <backend> <num> --repo <owner/name>` — return current PR
  identity metadata
- `/gish read <backend> <issue|pr> <num> --repo <owner/name>` — read an exact
  issue or PR
- `/gish edit <backend> <issue|pr> <num> --repo <owner/name>` — edit an exact
  local body
- `/gish create <backend> <issue|pr> ...` — create an exact approved object
- `/gish sync <backend> <issue|pr> <num> ...` — push an exact approved body
- `/gish comment-reply <backend> <pr> ...` — publish one approved inline reply
- `/gish comment-edit <backend> <comment-id> ...` — replace one approved
  review-comment body
- `/gish review-post <backend> <num> ...` — publish one approved top-level
  review body
- `/gish list [backend]` — list cached issue files
- `/gish` (no args) — detect backends from
  `git remote`, show available local files

## Actions

### `inspect-pr <backend> <num> --repo <owner/name>`

Query the selected provider for current PR identity metadata without changing
local refs or remote state. Return one normalized record:

```json
{
  "provider": "<backend>",
  "repository": "<owner/name>",
  "pr": 123,
  "queried_at": "<ISO-8601>",
  "head_repository": "<owner/name>",
  "head_ref": "<name>",
  "head_oid": "<full-oid>",
  "base_ref": "<name>",
  "base_tip_oid": "<full-oid>",
  "provider_diff_base_oid": null
}
```

For GitHub, pass `--repo <owner/name>` and request head-repository owner/name,
`headRefName`, `headRefOid`,
`baseRefName`, and `baseRefOid` in one `gh pr view` query. Set
`provider_diff_base_oid` only when the backend exposes that exact concept;
`null` is correct when it does not.
Never substitute a merge base, base-tip OID, branch name, local ref, or cached
remote-tracking ref for a missing provider field. Report query/authentication
failure without falling back to stale metadata.

### `read <backend> <issue|pr> <num> --repo <owner/name>`

1. Check if `<backend>/<repository>/<kind>/<num>.md` exists in repo root.
2. If yes, read and display its contents.
3. If no, fetch from remote:
   - **gh issue**: `gh issue view <num> --repo <owner/name> --json body,title`
   - **gh PR**: `gh pr view <num> --repo <owner/name> --json body,title`
   - **gitea**: attempt `gish` via xonsh (requires
     modden env), else instruct user to sync manually
4. Write fetched content to the exact repository/kind path above.

### `edit <backend> <issue|pr> <num> --repo <owner/name>`

1. Require the exact local file to exist. If it is absent, stop; `/gish edit`
   does not authorize a remote read. The user must separately request `/gish
   read <backend> <issue|pr> <num> --repo <owner/name>`.
2. User describes changes, or claude edits the md
   file directly.
3. Write updated content to `<backend>/<repository>/<kind>/<num>.md`.
4. Offer to sync (push changes to remote).

### Immutable publication input

Apply this boundary to `create`, `sync`, `comment-reply`, and `comment-edit`.
Reject a symlink or non-regular `--body-file`. Read its bytes once into a
mode-0600 temporary regular-file snapshot outside the repository, hash that
snapshot, and compare it with the approved digest. Pass only the snapshot path
to the backend command, then delete it. Never hash one path and later publish
from the mutable source path.

### `create <backend> <issue|pr>`

Required invocation:

```text
/gish create <backend> <issue|pr> --repo <owner/name> \
  --title <title> --body-file <path> --sha256 <digest>
```

PR creation additionally requires `--base-ref <ref> --base-oid <oid>
--head-repo <owner/name> --head-ref <ref> --head-oid <oid>`.

1. Require a current human message approving the exact object kind,
   repository, title, rendered body, digest, and create action.
2. Recompute the body digest and refuse on mismatch.
3. For PRs, verify the named base ref in the target repository and head ref in
   the approved head repository still resolve to the approved OIDs immediately
   before creation; stop on drift. Never identify a fork head by branch name
   alone.
4. Push the exact candidate to the exact repository:
   - **gh issue**: `gh issue create --repo <owner/name> --title "<title>"
      --body-file <snapshot>`
   - **gh PR**: `gh pr create --repo <owner/name> --base <base-ref> --head
      <head-owner>:<head-ref> --title "<title>" --body-file <snapshot>`
   - **gitea**: via xonsh + `gish` xontrib
5. Write response to `<backend>/<repository>/<kind>/<num>.md` using the
   number assigned by the remote.

### `sync <backend> <issue|pr> <num>`

Required invocation:

```text
/gish sync <backend> <issue|pr> <num> --repo <owner/name> \
  --body-file <path> --sha256 <digest>
```

1. Require a current human message approving the exact object kind,
   repository, number, rendered body, digest, and sync action.
2. Read the exact `--body-file <path>` and recompute its digest. Refuse on
   mismatch.
3. Push to the named repository and object kind:
   - **gh issue**:
      `gh issue edit <num> --repo <owner/name> --body-file <snapshot>`
   - **gh PR**:
      `gh pr edit <num> --repo <owner/name> --body-file <snapshot>`
   - **gitea**: attempt xonsh + `gish`, else instruct
     user to sync manually
4. Report success/failure.

This is a remote write. Never infer the repository from cwd or choose between
issue and PR based only on a colliding number. Generating or updating a local
PR-message file is not sync authorization.

### `comment-reply <backend> <pr-num>`

Publish one exact inline reply from a prewritten candidate:

```text
/gish comment-reply <backend> <pr-num> --repo <owner/name> \
  --parent-comment <id> --head <oid> --path <path> --line <line> \
  --side <LEFT|RIGHT> --body-file <path> --sha256 <digest>
```

Require a current human message approving every argument and the complete
rendered body. Apply the immutable publication-input contract and verify the
forge PR head still equals `--head`. For GitHub, publish the snapshot without
shell interpolation:

```text
gh api repos/<owner>/<repo>/pulls/<pr-num>/comments \
  -F body=@<snapshot> -f commit_id=<head> -f path=<path> \
  -F line=<line> -f side=<side> -F in_reply_to=<parent-comment>
```

If the backend cannot preserve these exact reply semantics, stop without a
direct-provider fallback.

### `comment-edit <backend> <comment-id>`

Replace one existing review-comment body from an immutable local candidate:

```text
/gish comment-edit <backend> <comment-id> \
  --repo <owner/name> --body-file <path> --sha256 <digest>
```

Require the current human message to approve the exact rendered body, digest,
backend, repository, comment ID, and edit action. Recompute the digest before
publication and refuse on mismatch. Do not infer this approval from commit
authorization, detection of a new commit, review remediation, or approval of
another comment. If the selected backend lacks comment editing, stop without
direct-provider fallback.

Use the selected backend adapter with the exact approved file. For GitHub:

```text
gh api repos/<owner>/<repo>/pulls/comments/<comment-id> \
  -X PATCH -F body=@<snapshot>
```

The repository and comment ID are embedded in the endpoint, and `-F
body=@<snapshot>` reads the digest-verified candidate. Other backends must
provide equivalent exact-file semantics or report the operation unavailable.

### `review-post <backend> <num>`

Publish one non-approving top-level PR review from an exact local Markdown
file. This operation is the first-class transport adapter for
`/code-review`; it is not authorization to review, edit, commit, or push Git
refs.

Required arguments:

```text
/gish review-post <backend> <pr-num> \
  --repo <owner/name> --body-file <path> --sha256 <digest> \
  --head <commit> --event comment --actor <login>
```

Read and follow `references/review-publication.md`. Refuse publication unless
the current human message approves the exact body, target, and non-approving
event; the body digest and reviewed head still match; and the selected backend
implements this operation. Never silently fall back to direct service calls
outside the adapter contract.

Run the deterministic adapter rather than reconstructing its checks:

```text
python <skill-dir>/scripts/review-post.py \
  --backend <backend> --repo <owner/name> --pr <pr-num> \
  --body-file <path> --sha256 <digest> --head <commit> \
  --event comment --actor <login>
```

### `list [backend]`

1. Glob `<backend>/*.md` (or all `*/` if no backend
   specified).
2. Display numbered list of cached issues/PRs.

## Backend detection

When no backend is specified, detect from
`git remote -v`:
- URLs containing `github.com` -> `gh`
- URLs containing a gitea hostname -> `gitea`
- Fall back to asking the user

## Environment notes

**GitHub (`gh`)**: works anywhere with the `gh` CLI
installed and authenticated. No special env needed.

**Gitea**: requires the `modden` dev env with
`py-gitea` available. Activate via one of:
- `nix develop -c xonsh` from modden repo
- `pyup modden; reloadxsh gish` from user's xonsh

When the gitea env is unavailable, write files locally
and instruct the user how to sync:
```
gish <num>        # from xonsh with gish loaded
gish gitea <num>  # explicit backend
```

## Symlink setup

To use this skill from other repos, symlink the
skill directory:

```bash
# from any repo root:
ln -s /home/goodboy/repos/ai.skillz/skills/gish \
      .claude/skills/gish
```

## Xontrib boundaries

The `gish` xontrib (`modden/xontrib/gish.xsh`)
currently supports:
- **issue body edit** — full read/edit/sync cycle
- **issue create** — interactive title + body
- **remote detection** — `parse_remotes()` for
  multi-service repos

**Not yet implemented** (future work):
- `gish comment <num>` — append/edit comments
- `gish pr <num>` — PR-specific operations
- `gish sync <num>` — explicit pull/push sync
- `gish review <be> <num>` — fetch PR review
  comments to local file (for AI skill consumption)
- `gish reply <be> <num>` — post review replies
  from local file to remote service
- `gish ci <be> <sha>` — check CI status
- sr.ht, GitLab, plain git backends
- standalone CLI (factor out from xontrib)

See [ROADMAP.md](ROADMAP.md) for the full phased
plan covering AI skill integration.

For operations beyond what `gish.xsh` supports,
fall back to the `gh` CLI directly for GitHub, or
instruct the user for other backends.

The skill-level `review-post` adapter is an exception to that generic
fallback: it has its own human-verification and immutable-input contract and
uses the backend commands documented in `references/review-publication.md`.
Do not replace it with an ad hoc review-posting command.
