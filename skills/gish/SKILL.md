---
name: gish
description: >
  Read, create, edit, and sync issues/PRs across
  git service backends (GitHub, Gitea, etc.) using
  local markdown files.
argument-hint: "[action] [backend] [number]"
disable-model-invocation: true
allowed-tools:
  - Bash(gh *)
  - Bash(git *)
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
source for this skill lives in `modden/.claude/skills/gish/`
and is symlinked into other repos.

See also:
- [backends.md](backends.md) — per-backend capabilities
- [format.md](format.md) — markdown file conventions

## Invocations

- `/gish read <backend> <num>` — read issue/PR
- `/gish edit <backend> <num>` — edit local md file
- `/gish create <backend>` — create new issue
- `/gish sync <backend> <num>` — push local to remote
- `/gish list [backend]` — list cached issue files
- `/gish` (no args) — detect backends from
  `git remote`, show available local files

## Actions

### `read <backend> <num>`

1. Check if `<backend>/<num>.md` exists in repo root.
2. If yes, read and display its contents.
3. If no, fetch from remote:
   - **gh**: `gh issue view <num> --json body,title`
     or `gh pr view <num> --json body,title`
   - **gitea**: attempt `gish` via xonsh (requires
     modden env), else instruct user to sync manually
4. Write fetched content to `<backend>/<num>.md`.

### `edit <backend> <num>`

1. Ensure local file exists (read first if needed).
2. User describes changes, or claude edits the md
   file directly.
3. Write updated content to `<backend>/<num>.md`.
4. Offer to sync (push changes to remote).

### `create <backend>`

1. Draft issue/PR body in markdown.
2. Push to remote:
   - **gh**: `gh issue create --title "..." --body "..."`
     or `gh pr create ...`
   - **gitea**: via xonsh + `gish` xontrib
3. Write response to `<backend>/<num>.md` using the
   number assigned by the remote.

### `sync <backend> <num>`

1. Read local `<backend>/<num>.md`.
2. Push to remote:
   - **gh**:
     `gh issue edit <num> --body-file <backend>/<num>.md`
     or `gh pr edit <num> --body-file <backend>/<num>.md`
   - **gitea**: attempt xonsh + `gish`, else instruct
     user to sync manually
3. Report success/failure.

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
# from tractor repo root:
ln -s /home/goodboy/repos/modden/.claude/skills/gish \
      .claude/skills/gish

# from piker repo root:
ln -s /home/goodboy/repos/modden/.claude/skills/gish \
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
- sr.ht, GitLab, plain git backends

For operations beyond what `gish.xsh` supports,
fall back to the `gh` CLI directly for GitHub, or
instruct the user for other backends.
