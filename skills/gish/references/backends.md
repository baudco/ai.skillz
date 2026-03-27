# Backend reference

Each backend maps to a local subdirectory
(`<backend>/`) containing cached issue/PR markdown
files named `<num>.md`.

## GitHub (`gh/`)

**Status**: full support via `gh` CLI

**CLI tool**: [`gh`](https://cli.github.com/)

**Capabilities**:
- issues: view, create, edit, comment, close
- PRs: view, create, edit, comment, review, checks
- API: `gh api repos/{owner}/{repo}/...`

**Common commands**:
```bash
# read issue body + title as JSON
gh issue view <num> --json body,title

# read PR body + title as JSON
gh pr view <num> --json body,title

# edit issue body from local file
gh issue edit <num> --body-file gh/<num>.md

# edit PR body from local file
gh pr edit <num> --body-file gh/<num>.md

# create issue
gh issue create --title "..." --body "..."

# create PR
gh pr create --title "..." --body "..."

# list issues
gh issue list --json number,title --limit 50

# list PRs
gh pr list --json number,title --limit 50

# add comment
gh issue comment <num> --body "..."

# view PR checks
gh pr checks <num>
```

**Env requirements**: `gh` installed + authenticated
(`gh auth login`). Works in any shell.

**Repos using this backend**:
- `tractor` (17 cached files in `gh/`)

## Gitea (`gitea/`)

**Status**: sync via `gish` xontrib using `py-gitea`

**Sync tool**: `gish` xontrib
(`modden/xontrib/gish.xsh`)

**Capabilities**:
- issues: view, create, edit body
- PRs: similar API via `py-gitea`

**Sync mechanism**:
The `gish` xontrib uses `py-gitea` to authenticate
and push/pull issue bodies. It reads a token from
`~/opsec/gitea/py-gitea.key`.

```bash
# from xonsh with gish loaded:
gish <num>          # edit issue (default: gitea)
gish gitea <num>    # explicit backend
gish gitea          # create new issue
```

**Env requirements**:
- modden dev env (`nix develop -c xonsh`)
- or `pyup modden; reloadxsh gish` from xonsh
- `py-gitea` package available
- API token at `~/opsec/gitea/py-gitea.key`

**Repos using this backend**:
- `piker` (26 cached files in `gitea/`)
- `modden` (2 cached files in `gitea/`)

## Future backends (stubs)

### sr.ht (`srht/`)

**CLI tool**: [`hut`](https://sr.ht/~emersion/hut/)
or REST API

**Status**: not yet implemented

**Notes**:
- sr.ht uses a mailing-list-based workflow
- `hut` provides issue tracker access
- REST API at `https://todo.sr.ht/api/...`

### GitLab (`gl/`)

**CLI tool**:
[`glab`](https://gitlab.com/gitlab-org/cli)

**Status**: not yet implemented

**Notes**:
- `glab` has similar UX to `gh`
- `glab issue view/edit/create` etc.
- `gish.xsh` has a TODO stub for gitlab

### Plain git (`git/`)

**Tools**: `git-bug`, email patches

**Status**: not yet implemented

**Notes**:
- `git-bug` stores issues in git refs
- email-based workflows via `git send-email`
- fully decentralized, no service dependency
