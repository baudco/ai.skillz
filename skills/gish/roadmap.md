# `gish` roadmap: cross-service review + AI skills

This doc captures the convergence plan between:

- `gish` xontrib (`modden/xontrib/gish.xsh`) -
  the existing local-file-first issue/PR mgmt tool
- claude-code skills (`/code-review-changes`,
  `/pr-msg`, `/commit-msg`, `/run-tests`) - AI
  workflow skills that currently hardcode `gh` CLI

The goal: make `gish` the common transport layer
for all git-service interactions, so AI skills
generate *content* and `gish` handles *sync*.

---

## Current state

### What `gish` does today

- Local markdown files as canonical source
  (`<backend>/<num>.md`)
- GitHub backend via `gh` CLI (full support)
- Gitea backend via `py-gitea` xontrib (issues)
- Backend detection from `git remote -v`
- Read/edit/create/sync/list operations
- Symlink-able into any repo

### What AI skills do today

- `/code-review-changes` - fetches PR review
  comments, triages, applies fixes, posts inline
  replies (hardcoded to `gh api`)
- `/pr-msg` - generates PR descriptions with
  cross-service ref-link stubs (doesn't submit)
- `/commit-msg` - generates commit msgs with
  regression context awareness
- `/run-tests` - runs tests with worktree venv
  awareness
- `/inter-skill-review` - meta skill for
  auditing cross-skill contracts

### The gap

AI skills talk directly to GitHub via `gh api`.
No abstraction for other services. Review
comments are posted immediately with no local
file trail. The `gish` local-file-first model
would solve all of this but `gish` doesn't have
review-comment operations yet.

---

## Architecture vision

```
┌─────────────────────────────────┐
│  AI skills (content layer)      │
│                                 │
│  /code-review-changes           │
│    - triage review comments     │
│    - apply code fixes           │
│    - generate reply content     │
│    - write regression context   │
│                                 │
│  /pr-msg                        │
│    - generate PR descriptions   │
│                                 │
│  /commit-msg                    │
│    - generate commit messages   │
│    - consume regression context │
└────────────┬────────────────────┘
             │ writes local md files
             ▼
┌─────────────────────────────────┐
│  gish (transport layer)         │
│                                 │
│  local files:                   │
│    <backend>/<num>.md           │
│    <backend>/<num>_review.md    │
│    <backend>/<num>_replies/     │
│                                 │
│  operations:                    │
│    gish review <be> <num>       │
│    gish reply <be> <num> <cid>  │
│    gish sync <be> <num>         │
│    gish pr <be> <num>           │
│    gish ci <be> <sha>           │
└────────────┬────────────────────┘
             │ backend-specific sync
             ▼
┌─────────────────────────────────┐
│  backends                       │
│                                 │
│  gh:    gh api / gh CLI         │
│  gitea: py-gitea / REST API     │
│  srht:  hut CLI / REST API      │
│  gl:    glab CLI / REST API     │
│  git:   git-bug / email patches │
└─────────────────────────────────┘
```

### Key principle

**AI skills never call service APIs directly.**
They write content to local files, then `gish`
syncs those files to whichever backends are
configured. This gives us:

- Offline drafting + review before posting
- Cross-service sync (same reply to GH + Gitea)
- Audit trail in the repo
- The `📎 commit pending` problem vanishes
  (local file gets updated, then synced)

---

## New `gish` operations needed

### `gish review <backend> <pr-num>`

Fetch review comments from a PR and write them
to local files.

**Output**: `<backend>/<num>_review.md` containing
all review comments in a structured format:

```markdown
<!-- review-meta
pr: 366
review_id: 3963983463
backend: gh
fetched: 2026-03-25T04:20:00Z
-->

## comment:<comment-id>
file: tractor/_runtime.py
line: 2017

Using a `bidict` for `_registry` means values
(addresses) must be unique...

### reply (pending)

> 🤖 *response authored by `claude-code`*

Good catch - switched to `bidict.forceput()`...

> 📎 commit pending
```

Each comment block is machine-parseable. The
`### reply` subsection is where AI skills (or
the human) write response content. Status is
tracked per-comment: `pending`, `posted`,
`updated`.

### `gish reply <backend> <pr-num> [comment-id]`

Post (or update) reply content from the local
review file to the remote service.

- If `comment-id` given, post just that reply
- If omitted, post all `pending` replies
- After posting, update status to `posted` and
  record the response comment ID

**Backend mapping**:
- `gh`: `gh api .../pulls/<N>/comments/<id>/replies`
- `gitea`: `POST /repos/.../pulls/<N>/reviews/<rid>/comments`
- `srht`: email reply to patch thread (TBD)
- `gl`: `POST /projects/:id/merge_requests/:mr/discussions/:did/notes`

### `gish ci <backend> <sha>`

Check CI/check-run status for a commit.

- `gh`: `gh api .../commits/<sha>/check-runs`
- `gitea`: `GET /repos/.../commits/<sha>/statuses`
- `gl`: `GET /projects/:id/pipelines?sha=<sha>`

### `gish pr <backend> <num>`

Full PR lifecycle: view, create, edit body.
Currently a TODO stub in the xontrib.

### `gish edit <backend> <num> [--ai-draft]`

Edit an issue or PR description with optional
AI-generated draft content. The workflow:

1. **Fetch** current content from the service
   via backend API (`gh api`, `py-gitea`, etc.)
   into a local tempfile.
2. **AI draft** (when `--ai-draft` is passed):
   run the appropriate AI skill (`/pr-msg` for
   PRs, `/commit-msg` patterns for issues) to
   generate a fresh draft, writing it alongside
   the fetched original.
3. **Open `$EDITOR`**: launch the user's editor
   (or `vimdiff old new` when a draft exists) so
   they can review, merge, and finalize.
4. **Sync back** on save: push the edited content
   back to the service via the same backend API.

This pattern ("AI-edits-then-editor") keeps the
human in the loop while letting AI skills do the
heavy drafting. It mirrors the existing
`gish edit` flow but adds the `--ai-draft` flag
as an opt-in AI assist step.

**Integration with `/pr-msg`**:
- `/pr-msg` generates to
  `.claude/skills/pr-msg/pr_msg_LATEST.md`
- `gish edit --ai-draft` would consume that file
  as the "new" side of the vimdiff
- The "old" side is whatever's currently live on
  the service
- After save, `gish` syncs the merged result back

**Backend considerations**:
- GitHub: `gh api` for fetch + update
- Gitea: `py-gitea` API calls
- sr.ht: `hg email` / API patches (body editing
  is limited for patch series)

### `gish watch <backend> <num> [--interval N]`

Poll a PR/patch for review state changes and
notify when a new review (human or bot) lands.
Cross-service abstraction so the same workflow
works regardless of where the PR was submitted.

**Core loop**:

1. **Snapshot** current review state on first run
   — fetch all reviews, record IDs + states +
   timestamps into a local state file.
2. **Poll** at `--interval` (default 60s) — re-fetch
   reviews, diff against snapshot.
3. **Detect transitions**: new review submitted,
   state change (pending → commented →
   changes_requested → approved), new inline
   comments on an existing review.
4. **Notify** — configurable via `--on-review`:
   - `bell` — terminal bell (default)
   - `notify-send` — desktop notification (linux)
   - `file` — write `.claude/review_ready.md`
     for claude-code hook pickup
   - `<cmd>` — arbitrary shell command
     (e.g. `claude --skill /code-review-changes`)
5. **Optionally exit** after first new review
   (`--once`) or keep watching for follow-ups.

**State file**: `<backend>/<num>_watch.json`

```json
{
  "pr": 428,
  "backend": "gh",
  "last_poll": "2026-03-25T22:20:00Z",
  "reviews": [
    {
      "id": 4010255289,
      "state": "COMMENTED",
      "author": "copilot-pull-request-reviewer[bot]",
      "submitted_at": "2026-03-25T22:20:39Z",
      "notified": true
    }
  ]
}
```

The `notified` flag prevents duplicate alerts on
restart. The `last_poll` timestamp enables
incremental comment fetches (`--since` style).

**Backend API mapping**:

| Service | Endpoint                                      | Notes                       |
|---------|-----------------------------------------------|-----------------------------|
| GitHub  | `GET /repos/{o}/{r}/pulls/{n}/reviews`        | full review objects w/ state |
| Gitea   | `GET /api/v1/repos/{o}/{r}/pulls/{n}/reviews` | similar shape to GH         |
| GitLab  | `GET /projects/:id/merge_requests/:mr/notes`  | notes API, filter by system |
| sr.ht   | `GET /api/patches/:id/events` (TBD)           | event-based, not review     |

**Normalized review struct** (cross-service):

```python
@dataclass
class Review:
    id: str           # service-specific
    state: str        # pending|commented|changes_requested|approved
    author: str       # login or email
    submitted_at: str # ISO 8601
    n_comments: int   # inline comment count
```

Each backend maps its native response into this
shape. The poll loop diffs on `(id, state)` tuples
— a state change on an existing ID counts as a
new event (e.g. reviewer initially comments, then
later approves).

**Integration w/ claude-code**:

The "poll → detect → handoff" bridge to claude:

1. `gish watch` writes `.claude/review_ready.md`
   when a new review lands:
   ```markdown
   <!-- review-ready
   pr: 428
   backend: gh
   review_id: 4010255289
   author: copilot-pull-request-reviewer[bot]
   state: COMMENTED
   submitted_at: 2026-03-25T22:20:39Z
   -->
   ```
2. A claude-code **hook** (or manual session
   startup check) detects this file and prompts:
   "PR #428 has a new review from copilot.
   Run `/code-review-changes`?"
3. After `/code-review-changes` completes (triage
   → fix → reply PATCH), it deletes
   `review_ready.md` — same single-use lifecycle
   as `review_context.md`.

**Multi-service watching**:

When a PR is submitted to multiple services (per
`pr-msg-meta` `submitted:` fields), `gish watch`
can poll all backends in parallel:

```
gish watch --all 428
# reads pr-msg-meta, finds gh=428 gitea=17
# polls both, notifies on first review from either
```

This is the cross-service analog of the existing
`gish review` fetch — same PR, multiple backends,
unified notification.

**Usage examples**:

```bash
# simple poll, terminal bell on review
gish watch gh 428

# desktop notify, check every 30s, exit on first
gish watch gh 428 --interval 30 --on-review notify-send --once

# write file for claude pickup
gish watch gh 428 --on-review file

# watch all backends where PR was submitted
gish watch --all 428

# fire-and-forget bg poll + auto-invoke claude
gish watch gh 428 --on-review \
  'claude -p "/code-review-changes 428"' &
```

---

## Phased implementation plan

### Phase 1: extract + abstract

**Goal**: decouple AI skills from `gh api` calls
without breaking current functionality.

- Add a `review-backends.md` to the gish skill
  documenting the per-service API shapes for
  review operations.
- Refactor `/code-review-changes` to write reply
  content to local files first, then call `gh`
  for posting as a separate step.
- The local file format becomes the contract
  between AI skills and `gish`.

### Phase 2: `gish review` + `gish reply`

**Goal**: review comment fetch/reply as first-class
`gish` operations.

- Implement `gish review gh <num>` in the xontrib
  (fetch + write local review file).
- Implement `gish reply gh <num>` (read local
  replies, post to GH, update status).
- Implement `gish review gh <num> --since <ts>`
  for incremental follow-up fetches (new/updated
  comments only). Each backend needs its own
  `since` filter strategy (see the review
  follow-up loop section under "How AI skills
  change").
- Update `/code-review-changes` skill to use
  `gish review` for fetching, `gish reply` for
  posting, and `gish review --since` for the
  follow-up round prompt.
- Add `gish ci gh <sha>` for CI baseline checks.

### Phase 2.5: `gish watch` (review polling)

**Goal**: close the gap between "review submitted"
and "dev picks it up" — especially for bot reviews
that land seconds after PR creation.

- Implement the poll loop w/ state file persistence
  (`<backend>/<num>_watch.json`).
- GitHub backend first (`gh api` reviews endpoint).
- Notification hooks: terminal bell, `notify-send`,
  file-based (`.claude/review_ready.md`).
- `--once` flag for CI/scripting use.
- Wire up `gish watch --all` to read `pr-msg-meta`
  `submitted:` fields for multi-backend polling.
- Add claude-code hook that checks for
  `review_ready.md` on session startup (or as a
  `user-prompt-submit-hook`).

### Phase 3: Gitea review backend

**Goal**: same review workflow on Gitea mirrors.

- Gitea's review API is structurally similar to
  GitHub's (`/repos/{owner}/{repo}/pulls/{index}/reviews`).
- Implement `gish review gitea <num>` and
  `gish reply gitea <num>`.
- Cross-service sync: run `/code-review-changes`
  once, post replies to both GH and Gitea.

### Phase 4: sr.ht + email patches

**Goal**: support mailing-list-based review.

- Very different model: patches are emailed,
  review happens via email replies.
- `hut` CLI for issue tracker, but patch review
  is email-native.
- May need a different abstraction: "compose
  email reply" rather than "post API comment".
- Local file format stays the same; the sync
  backend just generates email instead of API
  calls.

### Phase 5: `gish` as standalone CLI

**Goal**: `gish` becomes a proper CLI tool (not
just an xontrib) that works in any shell.

- Factor out the core logic from `gish.xsh` into
  a Python library (`modden.gish` or standalone
  `gish` package).
- Keep the xontrib as a thin shell-integration
  wrapper.
- The AI skills call the library directly (or
  via CLI) instead of constructing raw API calls.
- Ship as a `uv tool` / `pipx` installable.

### Phase 6: `gish` repo as skill home

**Goal**: whichever repo hosts the `gish`
codebase (modden, standalone `gish`, etc.)
becomes the **canonical home** for all
cross-service AI skills.

Today skills are scattered:
- global (`~/.claude/skills/`): `code-review-changes`,
  `inter-skill-review`, `py-codestyle`, `commit-msg`
- tractor: `commit-msg`, `pr-msg`, `run-tests`
- modden: `gish`
- piker: `commit-msg` + domain skills

The long-term direction: since `gish` is the
transport/sync layer that all these skills
depend on, it makes sense for the gish repo
to own the skill definitions too. The current
`~/.claude/skills/` → dotrc flow inverts to:

```
gish-repo/.claude/skills/
  commit-msg/
    SKILL.md           ← canonical generic
  code-review-changes/
    SKILL.md           ← canonical, uses gish
  pr-msg/
    SKILL.md           ← canonical, uses gish
  inter-skill-review/
    SKILL.md           ← canonical
  run-tests/
    SKILL.md           ← canonical (or per-repo)
  skill-factoring/
    SKILL.md           ← canonical
  skills-deploy/
    SKILL.md           ← canonical

other-repos/.claude/skills/
  commit-msg/
    SKILL.md           → symlink to gish-repo
    style-guide-reference.md  ← repo-specific
    msgs/                     ← repo-specific
  code-review-changes  → symlink to gish-repo
  pr-msg               → symlink to gish-repo
  ...
```

Symlink direction flips: instead of
repo → `~/.claude/` (global), repos symlink
to the gish repo. The global `~/.claude/skills/`
also symlinks to gish-repo (or gish-repo's
install step deploys there).

This gives us:
- Single source of truth for skill logic
- Skill updates ship with `gish` releases
- Repo-specific overrides (style guides, test
  mappings) stay local
- `gish` CLI + `gish` skills evolve together
  (transport + content layers in one repo)

**Open**: if `gish` stays in modden vs becomes
its own package, the skill-hosting story stays
the same — it's just a question of which repo
the symlinks point at. Factor the skills out
whenever the `gish` codebase itself is factored
(Phase 5).

---

## How AI skills change

### `/code-review-changes` becomes:

1. `gish review <be> <pr>` to fetch comments
2. Triage + apply fixes (unchanged)
3. Write replies to local review file
4. `/run-tests` to verify (unchanged)
5. Present to user for review + commit
6. `gish reply <be> <pr>` to post replies
7. After commit: update local file with hash,
   `gish reply <be> <pr> --update` to patch
8. **Prompt for follow-up review round**

### Review follow-up loop (step 8)

After posting replies + PATCHing commit hashes,
prompt the user: "Check for new review activity
on this PR?"

If yes:
- `gish review <be> <pr> --since <last-fetch>`
  to fetch only new/updated review comments
  posted after the previous round
- If new comments found, re-enter at step 2
  (triage) with the fresh batch
- If no new activity, done

This must be **backend-agnostic** via `gish`:
- `gh`: poll `gh api .../pulls/<N>/comments`
  filtered by `since=<ISO-timestamp>`
- `gitea`: `GET /repos/.../pulls/<N>/comments?since=<ts>`
- `gl`: `GET .../merge_requests/<N>/discussions`
  (filter client-side by `updated_at`)
- `srht`: check mailing list thread for new
  replies (TBD — likely `hut` or IMAP polling)

The key insight: reviewers often respond to
the bot's replies within minutes. Without the
follow-up prompt, the user has to manually
re-invoke `/code-review-changes` with the same
URL. The prompt closes the loop naturally and
makes multi-round reviews feel conversational
rather than batch-oriented.

`gish review --since` should also update the
local review file incrementally (append new
comment blocks, update status of existing ones
if the reviewer resolved/re-requested changes)
rather than re-fetching everything.

### `/pr-msg` becomes:

1. Generate PR description (unchanged)
2. Write to local file (unchanged)
3. `gish pr <be> create` to submit
4. Cross-service: repeat step 3 per backend

### Commit-ref footers become:

Instead of hardcoded GitHub URLs, `gish`
provides the commit-URL base per backend:

```python
def commit_url(backend, sha):
    templates = {
        'gh': 'https://github.com/{owner}/{repo}/commit/{sha}',
        'gitea': 'https://{host}/{owner}/{repo}/commit/{sha}',
        'srht': 'https://git.sr.ht/~{owner}/{repo}/commit/{sha}',
        'gl': 'https://{host}/{owner}/{repo}/-/commit/{sha}',
    }
```

---

## Skill factoring + deployment

Skills like `/commit-msg` evolve inside a single
repo then need to be shared. Today this is ad-hoc
(manual symlinks, copy-paste, orphaned dirs).
Two new meta-skills would formalize the process:

### The problem: mixed generic + repo-specific

Taking `/commit-msg` as the canonical example:

**Generic workflow** (belongs in parent scope):
- step flow: detect context → gather diff →
  analyze → write → credit footer
- regression context (`review_regression.md`)
- review context (`review_context.md`) + PATCH
- two-file output pattern (msgs/ + LATEST)
- `Bash(gh *)` for reply PATCHing

**Repo-specific** (must stay local):
- `style-guide-reference.md` (learned from
  *that* repo's commit history)
- `msgs/` dir (output artifacts)
- any repo-specific abbreviations, section
  markers, or subject-line conventions

Current state across repos:
```
~/.claude/skills/commit-msg/     → missing
tractor/.claude/skills/commit-msg/
  SKILL.md                       → most refined
  style-guide-reference.md       → tractor-specific
  msgs/                          → ~90 files
modden/.claude/skills/commit-msg/
  SKILL.md                       → MISSING
  style-guide-reference.md       → MISSING
  msgs/                          → ~45 files (orphaned)
piker/.claude/skills/commit-msg/
  SKILL.md                       → piker-specific
  style-guide-reference.md       → piker-specific
  msgs/                          → ~75 files
```

### `/skill-factoring`

A meta-skill (runs alongside `/inter-skill-review`)
that splits a skill into scope layers:

1. **Analyze** a repo-local skill to identify
   which parts are generic workflow vs
   repo-specific content.
2. **Extract** the generic SKILL.md to the parent
   scope (`~/.claude/skills/<name>/SKILL.md`),
   replacing repo-specific refs with hooks:
   ```
   **Repo style guide**: if a
   `style-guide-reference.md` exists alongside
   this SKILL.md, use it. Otherwise fall back
   to the global `py-codestyle` conventions.
   ```
3. **Leave** repo-specific sub-files in place.
4. **Verify** the factored skill works in both
   contexts: repo with local overrides, and
   repo with only the parent skill.

The inheritance model:
```
~/.claude/skills/commit-msg/
  SKILL.md              ← generic workflow
                           (steps, context files,
                           output pattern)

<repo>/.claude/skills/commit-msg/
  style-guide-reference.md  ← repo-specific
  msgs/                     ← repo-specific output
```

When claude loads `/commit-msg`, it reads the
generic SKILL.md from the parent scope and
discovers repo-local sub-files in the repo's
`.claude/skills/commit-msg/` dir. The SKILL.md
references them conditionally ("if present,
use it").

### `/skills-deploy`

Operational skill for deploying/linking skills
across repos:

1. **Promote**: take a refined repo-local skill,
   run `/skill-factoring`, push the generic
   SKILL.md to `~/.claude/skills/` (and
   canonically to `dotrc/dotrc/claude/skills/`).

2. **Bootstrap**: for a repo that's missing a
   skill (like modden's orphaned `/commit-msg`):
   - Verify the parent-scope SKILL.md exists
   - Generate repo-specific sub-files:
     * `style-guide-reference.md`: analyze the
       repo's recent N commits to learn its
       conventions (subject patterns, body style,
       common abbreviations)
   - Validate the deployed skill works with a
     dry-run against staged changes

3. **Sync**: when the parent-scope SKILL.md is
   updated, check which repos have local
   overrides that might conflict. Flag stale
   repo-local SKILL.md files that shadow the
   improved parent version (e.g. piker's
   `/commit-msg` might have its own step flow
   that's now behind tractor's).

4. **Audit**: `/inter-skill-review` already
   checks cross-skill contracts; extend it to
   also check cross-scope consistency (parent
   vs repo-local versions of the same skill).

### Relationship to existing skills

```
/inter-skill-review
  └─ audits cross-skill contracts (existing)
  └─ audits cross-scope consistency (new)

/skill-factoring
  └─ splits generic vs repo-specific (new)
  └─ runs after a skill is refined enough

/skills-deploy
  └─ promote: repo → parent scope (new)
  └─ bootstrap: parent scope → new repo (new)
  └─ sync: parent updates → repo check (new)
```

These three compose: `/inter-skill-review`
detects that a skill is missing or stale in a
repo, `/skill-factoring` splits the mature
version, `/skills-deploy` pushes it out.

### Backend-agnostic considerations

The factoring must account for backend-specific
content too. As `gish` replaces direct `gh api`
calls in skills:

- Generic SKILL.md says `gish reply <be> <pr>`
- Backend-specific details live in `gish`'s own
  `backends.md`, NOT in each skill
- A skill deployed to a gitea-only repo should
  work identically to one in a github repo
  because `gish` handles the transport

This means the factoring boundary is:
- **Parent scope**: workflow steps + `gish`
  commands (backend-agnostic)
- **Repo scope**: content conventions + output
  history (repo-specific)
- **`gish` scope**: backend API shapes + auth
  (service-specific)

---

## Open questions

- Should `gish` review files live in the repo
  root (`gh/366_review.md`) alongside issue files,
  or in `.claude/` since they're AI-workflow
  artifacts?
- How to handle review state across worktrees?
  The review file is about a PR (branch-scoped)
  but `gish` files live at repo root.
- sr.ht email workflow: can we generate
  `git send-email`-compatible reply drafts from
  the same local file format?
- Should `gish` track which backends a PR has
  been submitted to (expanding the `pr-msg`
  metadata comment pattern)?
- How aggressive should the follow-up review
  prompt be? Options: always prompt, only prompt
  when `fix` actions were taken (reviewer likely
  to respond), or only after bot-reviewers
  (copilot etc. tend to reply fast). Probably
  configurable per-backend or per-reviewer.
- For the `--since` incremental fetch: should
  `gish` persist the last-fetch timestamp in the
  local review file metadata, or derive it from
  the most recent comment timestamp already in
  the file?
- **Skill scope resolution**: when a skill
  exists in both `~/.claude/skills/` and
  `<repo>/.claude/skills/`, does claude-code
  shadow (local wins) or merge (both loaded)?
  The factoring model assumes conditional
  sub-file discovery — need to verify this is
  how the runtime actually works.
- **Style guide generation**: `/skills-deploy`
  bootstrap needs to auto-generate a
  `style-guide-reference.md` by analyzing a
  repo's commit history. How many commits to
  sample? Should it be a skill itself
  (`/analyze-commit-style`)?
- **Piker divergence**: piker's `/commit-msg`
  has its own evolved style (colon notation,
  financial domain terms). Should factoring
  preserve piker's local SKILL.md as an
  override, or merge its unique patterns into
  `style-guide-reference.md` and adopt the
  generic workflow from parent scope?
- **dotrc as canonical source**: global skills
  live in `dotrc/dotrc/claude/skills/` and
  deploy to `~/.claude/skills/`. Should
  `/skills-deploy promote` write to dotrc
  directly (and let dotrc's install mechanism
  sync to `~/`), or write to `~/.claude/` and
  let the user sync back to dotrc?
- **Watch polling interval**: what's the right
  default? 60s is polite to APIs but bot reviews
  (copilot) land in <30s — should `gish watch`
  start w/ a fast initial burst (5s for first
  2min) then back off to the configured interval?
- **sr.ht review detection**: sr.ht patches don't
  have a "review" concept — reviews happen via
  email replies to the patch thread. Can we poll
  the mailing list archive API, or do we need a
  local mail integration (`notmuch` / `mbsync`)?
- **Watch daemon vs one-shot**: should `gish watch`
  be a long-running daemon (systemd user unit?)
  or purely interactive? A daemon could watch
  all open PRs across all repos, but that's a
  lot of API calls. Maybe a hybrid: interactive
  by default, `--daemon` flag for persistent bg
  mode w/ rate limiting.
