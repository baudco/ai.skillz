# `claude-reply` — reference notes

An nvim integration that turns Claude Code's **Ctrl-G "edit last
response"** buffer into an email-style, quote-and-reply composer.
Captured while building it; verified against Claude Code **2.1.156**.

> ⚠️ This is **not** a Claude Code slash-command — it's a Neovim
> plugin spec (`claude-reply.lua`). It deploys by symlinking into your
> nvim config, **not** via `deploy-skill.sh command`. See `DEPLOY.md`.

## TL;DR

Enable Claude Code's `externalEditorContext` ("Show last response in
external editor"). Then **Ctrl-G** opens your last response in nvim as
`# `-commented reference text above a *"Write your reply below this
line"* marker. This plugin, firing on the `claude-prompt-*.md` temp
buffer, lets you:

- `]m` / `[m` — jump between Claude's response **sections** (in the
  reference region), like `]m`/`[m` jump methods in code.
- `\e` (normal) — **pull** the section under the cursor *down* below
  the marker as a `gq`-wrapped (your `textwidth=69`) `> ` blockquote,
  cursor parked underneath in insert mode for your inline reply.
- `\e` (visual) — pull the selected reference lines.

Only what ends up **below** the marker is sent back to Claude, so you
quote just the bits you're answering — like replying to an email.

## The mechanism (verified, CC 2.1.156)

Decompiled from the bundled binary (`bin/.claude-unwrapped`):

- **Ctrl-G** runs handler `xV` → `vk(input, pasted, context)`. The
  editor is resolved `settings.editor ?? $VISUAL ?? $EDITOR` (here:
  `nvim`), opened as `nvim <file>` (terminal editors get `+<line>`
  only from the transcript-view path, not this one). The **entire
  file is read back** as the next message.
- The temp file is **`claude-prompt-<uuid>.md`** (markdown) in Claude's
  temp dir; auto-unlinked after the editor exits.
- With `externalEditorContext` **on** (default **off**), `Tt_(context)`
  composes the buffer:
  ```
  # ─── Claude's last response (for reference; removed on save) ───   ← HEADER marker
  # <every response line, '# '-prefixed; bare '#' == original blank>
  # ─── Write your reply below this line ──────────────────────────   ← REPLY marker

  <empty reply area>
  ```
  Box char is U+2500 (─). The reference is truncated to the **last 50
  lines**; if truncated the first line is `# … (earlier output
  truncated)`.
- On save, `Vt_()` finds the REPLY marker and **discards everything at
  and above it** — only text below it is sent. So the marker line must
  survive verbatim (exactly one occurrence), and anything you want
  sent must sit below it. (The HEADER/`#`-reference above is never
  re-sent — that's why `\e` copies a `> ` quote *down*.)
- **Marker detection anchors on the box rule** (`# ─`, U+2500), not the
  bare phrase. Claude Code prefixes every response line with `# `, so a
  response that *mentions* "Write your reply below this line" in prose
  (these docs do!) starts `# W…`, never `# ─…` — and is correctly
  skipped. Matching only the substring would (and once did) mistake
  that prose for the marker and truncate the navigable region there.
- Builtin `ftplugin/markdown.vim` already sets `comments=…,n:>` and
  `formatoptions+=tcqln`; nvim's own default `comments` also has
  `n:>`. So `gq` over `> ` lines reflows keeping the `> ` leader. The
  plugin still asserts `tw=69` + `q`,`n` in `fo` + `n:>` in `comments`
  (buffer-local, snapshot/restored) and clears `formatexpr`/`formatprg`
  during the wrap, so the result is byte-identical to a manual `gqap`.

## The gotcha (the headline learning)

A common (wrong) suggestion for "format my Ctrl-G buffer" is a
`PostToolUse` hook with `matcher: "Write|Edit"` running `prettier`.
That **cannot** work: `PostToolUse` fires after Claude's **Write/Edit
tool** calls (files Claude edits), never around the external-editor
buffer. There is **no hook** for the Ctrl-G buffer at all. The only
interception points are the editor itself (`settings.editor` /
`$VISUAL` / `$EDITOR`) — so the right lever is nvim, keyed off the
`claude-prompt-*.md` filename. No wrapper script needed: nvim *is* the
editor, so its real `gq` gives exactly your vimrc wrapping.

## UX / bindings

- **`\e`** ("edit") is buffer-local — it only shadows anything else
  inside `claude-prompt-*.md`. (`\q` was avoided: it's your global
  `ListToggle` quickfix toggle, `nav.lua:116`.) Everything routes
  through `<Plug>(ClaudeReplyPull)`, so rebinding is a one-line edit.
- The reference is **de-hashed to plain markdown** on open — the `# `
  prefixes between the markers are stripped, so nvim's builtin markdown
  **syntax** highlights it (headings, lists, fences, code; see
  `claude_reply_highlight` below). Safe because Claude bounds the send
  by the marker *line*, not the `#`, so no re-injection is needed;
  marker lines are kept verbatim and the buffer is marked un-modified
  so a bare `:q` still aborts cleanly.
- The reference region is soft-wrapped (`wrap`/`linebreak`/
  `breakindent`, `↪` showbreak) for reading and folded **by section**
  (`foldmethod=expr`, folds open; `<Space>`/`zM`/`zR` toggle).
- A "section" is a maximal run of non-blank reference lines; a
  markdown heading also starts a new section.
- **No-op safety:** if `externalEditorContext` is off (no markers in
  the buffer), the module does nothing — your global maps and built-in
  `]m` motion are untouched.

## Configuration

- **`vim.g.claude_reply_colorscheme`** — set to a colorscheme name to
  use a distinct scheme while editing a `claude-prompt-*.md` buffer,
  e.g. in your nvim config:
  ```lua
  vim.g.claude_reply_colorscheme = "habamax"
  ```
  Because Ctrl-G spawns a dedicated, single-buffer nvim, applying it
  globally there is self-contained; the module also restores your
  previous scheme on buffer-leave (a `BufEnter`/`BufLeave` pair) so it
  stays tidy if you ever open one of these buffers inside your main
  nvim. Unset (default) → no change.
- **`vim.g.claude_reply_highlight`** — how the de-hashed reference is
  highlighted:
  - `"syntax"` *(default)* — nvim's robust builtin markdown **syntax**,
    and **treesitter is detached for this buffer**. This is deliberate:
    a broken or absent markdown TS parser (common — an empty
    `nvim-treesitter/parser` dir is enough) crashes the highlighter on
    every redraw of the compose buffer with
    `treesitter.lua: attempt to call method 'range' (a nil value)`.
    Legacy syntax never has that problem and renders markdown fine.
  - `"treesitter"` — leave whatever your config attached (use only if
    your markdown TS actually works).
  - `"off"` — no highlighting.

## Known limitations

- `gq` reflows a pulled section as one paragraph — if it mixes a
  heading + bullets + prose with no blank lines, they merge (exactly
  what manual `gq` over those lines would do). Pull prose; trim after.
- Fenced code (```` ``` ````) inside a pulled section gets reflowed by
  `gq` (it doesn't understand fences). A future v2 can skip fenced
  runs.

## Out of scope (future)

The transcript view's **`v`** key writes the *whole* transcript to
`cc-transcript-<ts>.txt` and opens it read-only (`{`/`}` already
navigate messages there). A separate autocmd could pretty-print that
too — not done here.

## Files

- `claude-reply.lua` — the module (canonical here; symlinked to
  `~/repos/dotrc/dotrc/nvim/lua/plugins/claude-reply.lua` →
  `~/.config/nvim/lua/plugins/`). Self-contained lazy.nvim spec: runs
  `setup_autocmds()` at import, returns `{}` (no remote plugin).
- `DEPLOY.md` — symlink + the one-time `/config` toggle.

## Roadmap

Follow-up ideas (older-reply quoting, a transcript side-panel,
cross-provider profiles, a plenary test suite, proper lazy.nvim
packaging) are scoped with feasibility verdicts in
[`plans/claude/claude-reply-roadmap.md`](../../plans/claude/claude-reply-roadmap.md).
