Add picker UX round + deep reply search to `claude-reply`

User-feedback wave on the dialog/turn pickers plus a deep
content-search mode across dialogs, projects and harnesses.

- rebind the dialog picker to `\d` ("dialog"); all user-facing keys
  configurable via `g:claude_reply_key_{pull,replies,dialogs}`
  (buffer-local shadows only); `:ClaudeReplyDialogs` (+ the old
  `:ClaudeReplySessions` alias).
- colorize picker rows via telescope display-fn highlights:
  `[cc]`/`[oc]` badges, date, project — new default-linked hl groups
  `ClaudeReplyCc/Oc/Date/Proj` (re-applied on `ColorScheme`).
- prefix picker prompt titles with the scope: `⟦pwd⟧` vs `⟦ALL⟧`.
- `<C-o>` back-out from the turn picker restores the dialog picker's
  typed query (`default_text` plumbing; `<C-a>` scope toggle keeps it
  too); first `<C-c>` clears the filter, second closes.
- add 45s TTL caches for session lists + foreign-session turn
  fetches — kills the `<C-o>`/preview-hover lag (the planned py
  daemon's warm index is the endgame fix).
- deep content search: `<C-g>` in the dialog picker opens a flat
  turn-level corpus picker whose `ordinal` carries each turn's FULL
  text (fuzz reply content cross-project/harness; query carries
  over); `:ClaudeReplyGrep {pat}` (bang = all projects) pre-narrows
  with an external grepper (`g:claude_reply_grepper`, `rg` default,
  `grep` fallback) on claude jsonl + `oc-last-reply.py --grep`
  (case-insensitive substring) on the opencode store.
- `oc-last-reply.py`: add `--dump` (all turns of all scoped sessions,
  one spawn) and `--grep PAT`; `--all-dirs` now applies to both.
- plans: `standalone-plugin-plan.md` (factor out of `commands/` into
  `ai-reply.nvim`-style standalone repo; py side stays a zero-dep
  single file until the daemon lands — naming/host decision pending);
  `py-extension-plan.md` gains the remote-host requirement (decoupled
  RPC daemon == location-transparent; nvim `--listen`/`--server`,
  nvr refs) + modden wks-spawned daemon lifecycle.
- project-grouped "tree" view as the `\d` default: dialogs indented
  under `(repos/<proj>)` header rows, groups MRU-ordered by their
  newest dialog; headers are telescope pseudo-rows with an EMPTY
  ordinal (visible on empty prompt, vanish when typing — flat fuzzy
  takes over; telescope has no native tree), not openable, absent
  from the `vim.ui.select` fallback; `<C-t>` toggles tree ↔ flat
  live, `g:claude_reply_dialogs_grouped = false` for flat default.
- scope tag shows the ACTUAL project label (`⟦repos/ai.skillz⟧`),
  not the literal word "pwd".
- fix the "stray G" bug: every picker→picker hop (`<CR>`, `<C-a>`,
  `<C-t>`, `<C-g>`, `<C-o>`) now `vim.schedule()`s the reopen —
  same-tick close/reopen let the trigger key's tail leak into the
  new prompt (also corrupting the carried-over deep-search query).
- verify headless: 10/10 (keys incl. `\d`, cache hit after breaking
  the stub, deep corpus 4 turns, grep narrows to 2 via real rg +
  py-side filter, paged w/ title tag, graceful no-match) + 5/5 tree
  round (no headers in fallback, real pwd label in the tag);
  real-config: dialog picker prefilled with retained query, deep
  picker opens, hl groups defined, live tree view = 11 project
  headers grouping 33 dialogs in ⟦ALL⟧ scope.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
