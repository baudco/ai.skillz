# Plan: cross-harness session picker for `claude-reply`

## Context

The `\r` prior-reply picker (shipped) fuzzes over turns of the
*current* session only. This extends the idea one level up: browse and
fuzzy-search **sessions** — across BOTH harnesses' stores — then drill
into any session's turns for the existing page/quote workflow. Use
case: "that explanation claude gave me last week in the dotrc session"
or "the opencode session where gpt audited lns" — quote it into the
conversation you're composing NOW, regardless of which harness spawned
the buffer (quoting is just text → cross-harness pollination is free).

## Research findings (verified 2026-07-06)

- **claude sessions**: `~/.claude/projects/<slug>/<uuid>.jsonl`
  (25 slugs live). Titles: LAST `{"type":"custom-title"}` (from
  `/rename`) or `{"type":"ai-title"}` line — not guaranteed present;
  fallbacks: LAST `{"type":"last-prompt","lastPrompt":…}` line, then
  filename. `~/.claude/history.jsonl` = per-prompt
  `{display, project, sessionId, timestamp}` log (cheap cross-project
  index, optional accelerator). **`~/.claude/sessions/<pid>.json`**
  maps LIVE pids → `{sessionId, cwd, name, status}` — noted for later
  (exact current-session identification via ancestor-pid walk);
  not required for this feature.
- **opencode sessions**: sqlite `session` table (id, title, directory,
  parent_id, time_updated) — trivial to list; child/subagent sessions
  have `parent_id` set (exclude).

## Design

Two-stage picker, both stages telescope-when-available with
`vim.ui.select` fallback:

1. **Stage 1 — sessions** (`\R`, `:ClaudeReplySessions`): merged list
   from both stores, `[cc]`/`[oc]` badges, newest-first:
   `[oc] 07-03 20:38  Audit system design plan…  (repos/lns)`.
   Default scope = current project (cwd slug / cwd-prefixed dirs);
   `<C-a>` toggles all-projects scope. Preview pane = the session's
   last reply (lazily fetched + cached per entry).
   `<CR>` → stage 2 for that session.
2. **Stage 2 — turns**: the EXISTING `pick_reply` parameterized with a
   source; same `<CR>` page / `<C-q>` quote actions; `<C-o>` goes back
   to stage 1. Foreign-session pages tag the header
   `⟨<title> #N/M⟩` so you can see whose reply you're reading.

## Changes

- `oc-last-reply.py`: `--sessions` (JSON session list for --cwd's
  project; `--all-dirs` drops the filter) and `--session <id>`
  (constrains `--list`/last-reply to an explicit session).
- `claude-reply.lua`:
  - `list_sessions(all_scope)` — claude scan (slug dir or all slugs,
    newest-N cap for all-scope; title extraction per findings) +
    opencode `--sessions`; merged/sorted.
  - `fetch_turns(buf, src)` — optional explicit source
    `{provider, path|session}` (nil = current behavior).
  - `M.pick_session(buf)` + `\R` map; `pick_reply(buf, src)` gains the
    source param + `<C-o>` back-nav; `set_reference` gains an optional
    session label for the header tag.

## Verification

- py: fixture db w/ 2 top-level sessions in 2 dirs + a child session →
  `--sessions` scoping, `--all-dirs`, `--session <id> --list`.
- lua headless: claude `list_sessions` title/fallback extraction +
  mtime order; two-stage `vim.ui.select` fallback end-to-end (session →
  turn → reference paged w/ session tag); **cross-harness**: opencode
  buffer paging in a CLAUDE session's turn; `\r`/claude regressions.
- real-config smoke: `\R` opens a Telescope session list fed by both
  real stores.
