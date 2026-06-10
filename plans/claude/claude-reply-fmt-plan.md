# Plan: email-style quote-reply for Ctrl-G "edit last response" in nvim

## Context

With `externalEditorContext` enabled, **Ctrl-G** in Claude Code opens your
last response in nvim so you can compose the next message with it in view.
Today that response is dumped as raw `#`-commented lines that are *discarded
on save* — no wrapping to your textwidth, no way to quote it email-style and
reply inline per section. This adds exactly that, as a self-contained nvim
module triggered on the `claude-prompt-*.md` temp buffer, plus a reproducible
package in this repo. Outcome: press Ctrl-G, scan Claude's response by
section (`]m`/`[m`), pull the section you want to answer (`\e`) down as a
`gq`-wrapped `> ` blockquote, type your reply under it; only the quoted +
typed text below the marker is sent back.

## Verified mechanism (Claude Code 2.1.156 binary)

- Ctrl-G handler `xV` → `vk(input, pasted, context)`; editor resolved
  `settings.editor ?? $VISUAL ?? $EDITOR` (yours: `nvim`).
- Input temp file is **`claude-prompt-<uuid>.md`** (markdown), opened as
  `nvim <file>` (no `+line`); the **whole file is read back** as the message.
- With `externalEditorContext` ON (**default false**), `Tt_(context)` writes:
  ```
  # ─── Claude's last response (for reference; removed on save) ───   ← HEADER marker
  # <every response line, '# '-prefixed; bare '#' = original blank>    (last 50 lines)
  # ─── Write your reply below this line ──────────────────────────   ← REPLY marker

  <empty reply area>
  ```
  Box char is U+2500 (─). Truncation (>50 lines) prepends `# … (earlier output truncated)`.
- On save, `Vt_()` finds the REPLY marker and **discards everything at/above
  it** — only text *below* the marker is sent. The marker line must be kept
  verbatim (exactly one occurrence). If `externalEditorContext` is OFF, the
  buffer has no markers (raw input) → the module must **no-op**.
- Builtin `ftplugin/markdown.vim` already sets `comments=...,n:>` and
  `formatoptions+=tcqln`, so nvim's `gq` over `> ` lines reflows keeping the
  `> ` leader out of the box. `~/.vimrc` (sourced before lua) gives global
  `textwidth=69`, `formatoptions=qn1`. Leader is `\`.

## Decisions (confirmed)

- **Behavior: empty + on-demand pull.** Reference stays above the marker
  (soft-wrapped, foldable by section); reply area starts empty, cursor parked
  there. `\e` pulls the section under the cursor down as a wrapped `> ` quote.
- **Nav keys: `]m` / `[m`** between Claude's response sections (vim's
  method-motion, free in markdown; you named these).
- **Pull key: `\e`** ("edit"), buffer-local, collision-free (only a
  commented-out ALE line at `~/.vimrc:364`). Also bound in visual mode to
  pull a selection of reference lines. Routed via `<Plug>(ClaudeReplyPull)`.
- **Packaging: dotrc + ai.skillz.** Canonical source in this repo under
  `commands/claude-reply/`, symlinked into the nvim config (branch-in-term
  pattern).

## Files to create

### 1. The nvim module — `commands/claude-reply/claude-reply.lua` (canonical)

One self-contained lazy.nvim spec file (returns a local spec, does all work in
`init`). Symlinked to `~/repos/dotrc/dotrc/nvim/lua/plugins/claude-reply.lua`
(→ `~/.config/nvim/lua/plugins/`), auto-loaded by the existing
`{ import = "plugins" }` glob — no change to `init.lua`/`lazy.lua`.

Spec shape (no remote plugin to fetch):
```lua
return {
  dir = vim.fn.stdpath("config"), name = "claude-reply", lazy = false,
  init = function() require("claude-reply.core").setup_autocmds() end,
}
```
To keep it a **single deployable file**, register the module table in
`package.loaded` from within `init` (so `foldexpr` and the spec share it)
rather than a second `lua/` file — i.e. define `local M = {...}` and
`package.loaded["claude-reply.core"] = M` inside the file, and set
`foldexpr = "v:lua.require'claude-reply.core'.foldexpr(v:lnum)"`. (Two-file
split — `lua/claudereply.lua` lib + thin spec — is the clean alternative if a
single file feels cramped; either is fine.)

Functions (per the validated design):
- `find_markers(buf)` → `{header, reply}, lines` via plain-text `find` on
  `"Write your reply below this line"` / `"Claude's last response"`. Abort if
  `reply == nil` (no-op path).
- classifiers: `ref_is_blank` (`^#%s*$`), `ref_is_heading` (`^# #+%s`),
  `is_marker`; `strip_prefix` (`"# x"→"x"`, `"#"→""`).
- `section_bounds_at(lines, lo, hi, cur)` — section = maximal run of non-blank
  reference lines; a heading line also starts a new section.
- `nav_section(buf, dir)` — `]m`/`[m`; jumps to next/prev section **start**,
  **confined to the reference region** (above the REPLY marker).
- `quote_prefix` (`"x"→"> x"`, `""→ bare ">"` — bare `>` survives your `\w`
  trailing-strip and reflows cleanly) → `pull_section(buf, orig_lines)`:
  append blank separator + quoted lines + trailing blank below the marker,
  reflow with real `gq`, park cursor on the trailing blank (then `startinsert`
  — droppable if you prefer normal mode).
- `pull_under_cursor` / `pull_visual` entry points.
- `with_format_opts(buf, fn)` — snapshot/restore **buffer-local** `textwidth`
  (=69), `formatoptions` (ensure `q`,`n`), `comments` (ensure `n:>`), then run
  `vim.cmd("normal! {s}GV{e}Ggq")`. Buffer-local options → no leak to other
  buffers. This is the one faithful way to match a manual `gqap`.
- `setup_folds` — buffer-scoped `foldmethod=expr` + `foldexpr` folding the
  reference region by section, `foldlevel=99` (folds **open**); `<Space>`
  (your `za` map) toggles a section.
- `setup_buffer` — idempotent (`vim.b.claude_reply_ready` guard); set
  `wrap/linebreak/breakindent` + `showbreak` on the reference for readability
  (do **not** hard-wrap it — it's discarded and `# `-prefixed); park cursor
  below the REPLY marker; install buffer-local maps.
- `setup_autocmds` — augroup `{clear=true}`; `BufReadPost,BufWinEnter` on
  `pattern="claude-prompt-*.md"` (matches path tail in any tmpdir); re-asserts
  window-local wrap/folds on re-show, full setup once per buffer.

Edge cases handled: no REPLY marker → no-op (raw-input / `externalEditorContext`
off); cursor on a marker; empty reference; repeated/ordered pulls; truncation
line; **code fences inside a pulled section get reflowed by `gq` — documented
limitation** (pull prose; v2 can skip ``` ``` `` runs).

### 2. `commands/claude-reply/README.md`

Design/reference notes mirroring `commands/branch-in-term/README.md`: the
verified Ctrl-G mechanism above, the `claude-prompt-*.md` / marker / `Vt_`
strip contract, why pure-nvim (vs the misleading "prettier PostToolUse hook"
suggestion — that hook fires on Write/Edit *tool* output, never on the
external-editor buffer, so it cannot do this), and the `\e`/`]m`/`[m` UX.

### 3. `commands/claude-reply/DEPLOY.md`

Install steps (mirrors branch-in-term DEPLOY.md style):
1. Symlink `claude-reply.lua` → `~/repos/dotrc/dotrc/nvim/lua/plugins/claude-reply.lua`
   (note: this is an **nvim** integration, not a Claude slash-command, so
   `deploy-skill.sh command` does **not** apply — document the symlink).
2. Enable the buffer in Claude Code: **`/config` → toggle "Show last response
   in external editor"** (`externalEditorContext`, per-user, default off). This
   is what makes Ctrl-G include the response.
3. Restart nvim is unnecessary (loaded fresh each Ctrl-G); restart/`:Lazy
   reload` only after editing the spec.

## Verification

1. Fixture: write `/tmp/claude-prompt-TEST01.md` with HEADER marker, a
   truncation line, a long paragraph, a `## heading` + two bullets, a final
   paragraph, the REPLY marker, and a trailing blank.
2. `nvim /tmp/claude-prompt-TEST01.md` → ft=markdown; reference soft-wrapped
   (`↪` showbreak); cursor parked **below** the REPLY marker; folds present but
   open. `zM`/`zR`/`<Space>` fold sections; reply area never folds.
3. From the reply area `[m`/`]m` walk section starts upward/downward; a heading
   mid-run splits sections; nav never crosses below the marker.
4. Cursor in the first paragraph, `\e` → section appended below the marker as
   `> `-lines **hard-wrapped at 69**, blank-separated, cursor parked on a fresh
   blank after it (insert mode). Typed reply hard-wraps at 69.
5. Visual-select the two bullets, `\e` → pulled as one wrapped `> ` block after
   the prior quote+reply.
6. `:w`, then inspect lines from the REPLY marker down (e.g. `tail -n
   +<lineno>`): marker preserved verbatim (one occurrence); only quotes +
   typed reply below it; nothing above leaks.
7. `:split` → wrap/folds re-applied, no duplicate maps, no second park.
8. Marker-less `/tmp/claude-prompt-RAW.md` → module no-ops; global `\q`
   ListToggle and built-in `]m` motion still work.
9. End-to-end: in a real session, `/config` enable, Ctrl-G, exercise `\e`,
   save, confirm the sent message is the quoted+reply text only.

## Notes

- First execution step: also copy this plan to `plans/claude/claude-reply-fmt-plan.md`
  (repo convention) and, after executing, write `plans/claude/claude-reply-fmt-plan.summary.md`.
- Out of scope (mention in README): the transcript-view `v` key writes
  `cc-transcript-*.txt` (full transcript, read-only; `{`/`}` already navigate
  messages) — a separate, optional autocmd target later.
