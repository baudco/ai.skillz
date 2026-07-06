Add `\R` cross-harness session picker to `claude-reply`

Stage-1 fuzzy picker over sessions from BOTH harness stores, drilling
into the existing turn picker — quote any harness's reply into any
conversation. Also fix the REAL opencode extra-line bug and write the
py-extension research plan.

- fix opencode trailing blank line (the user-visible "extra line"):
  `vim.fn.writefile` always appends a trailing newline and opencode's
  `le()` only strips it from SINGLE-line content — multi-line prompts
  kept it, rendering an extra blank line in the prompt box (claude
  strips its own via `Vt_`, hence "opencode-only"). `oc_write` now
  writes binary-mode (`'b'`, no trailing NL) for content and a lone
  newline only for the cleared case (clear-not-abort preserved); also
  strip the draft's leading blanks at injection.
- `oc-last-reply.py`: add `--sessions` (JSON session list, cwd-scoped
  or `--all-dirs`; top-level only) and `--session <id>` targeting for
  `--list`/last-reply.
- `claude-reply.lua`:
  - `list_sessions(all_scope)`: claude jsonl enumeration (cwd slug or
    all slugs, newest-30 cap on all-scope) with titles via two batched
    greps (LAST `custom-title`/`ai-title`, `last-prompt` fallback,
    uuid-prefix last resort) merged with opencode `--sessions`;
    `[cc]`/`[oc]` provider tags, newest-first across sec/ms epochs.
  - `fetch_turns(buf, src)` + `oc_json()` helper: explicit
    `{provider, path|session}` sources; `set_reference(..., label)`
    tags foreign pages `⟨<title> #N/M⟩`.
  - `M.pick_session` (`\R`, `:ClaudeReplySessions`): telescope picker
    w/ lazy cached last-reply preview, `<C-a>` scope toggle, `<CR>` →
    `pick_reply(buf, src)` stage 2 w/ `<C-o>` back-nav;
    `vim.ui.select` fallback for both stages.
- research + write `plans/claude/py-extension-plan.md`: pynvim
  old-vs-new-style rplugins explained (manifest/`:UpdateRemotePlugins`
  wart; core proposes replacing rplugins with plain "remote modules"),
  NO trio/anyio nvim client exists (PyPI probed), recommended option =
  standalone anyio-native msgpack-rpc client daemon (modden/gish
  friendly) — BLOCKED on user brain-dump (questions listed).
- verify headless: 4/4 trailing-newline checks (incl. simulated `le()`
  semantics), 14/14 session-picker checks (merge order across sec/ms,
  title fallbacks, cross-harness stage-2: claude buffer paging an
  opencode turn + `\e` quoting it, label tag swap, `\R` map), 6/6
  claude regression; real-config smoke: 2 scoped / 33 all-scope
  sessions from the real stores, Telescope session picker opens.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
