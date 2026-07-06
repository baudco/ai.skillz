# `claude-reply` — reference notes

An nvim integration that turns Claude Code's **Ctrl-G "edit last
response"** buffer into an email-style, quote-and-reply composer.
Captured while building it; verified against Claude Code **2.1.156**.

> ⚠️ This is **not** a Claude Code slash-command — it's a Neovim
> plugin spec (`claude-reply.lua`). It deploys by symlinking into your
> nvim config, **not** via `deploy.sh command`. See `DEPLOY.md`.

## TL;DR

Enable Claude Code's `externalEditorContext` ("Show last response in
external editor"). Then **Ctrl-G** opens your last response in nvim as
`# `-commented reference text above a *"Write your reply below this
line"* marker. This plugin, firing on the `claude-prompt-*.md` temp
buffer, lets you:

- `]m` / `[m` — jump between Claude's response **sections** (in the
  reference region), like `]m`/`[m` jump methods in code.
- `\e` (normal) — **pull** content under the cursor *down* below the
  marker as a `gq`-wrapped (your `textwidth=69`) `> ` blockquote,
  cursor parked underneath in insert mode for your inline reply.
  Granularity is do-what-I-mean: on a **list item** (bullet/numbered,
  any nesting depth) it pulls *just that item* plus its indented
  children — quote only what you're answering, send fewer tokens; on a
  heading or prose line it pulls the whole section. (Whole section
  from an item: cursor on the heading, or V-select.)
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
- **The reference is hard-capped at 50 lines** by Claude Code itself
  (`rh4=50` in the binary — no setting changes it), with a sentinel
  first line `… (earlier output truncated)`. The plugin **re-inflates**
  a truncated reference from the session transcript on disk
  (`~/.claude/projects/<cwd-slug>/<uuid>.jsonl`, where the slug is the
  cwd with every non-alphanumeric → `-`): it reconstructs the last
  reply the same way Claude's context builder does (all assistant text
  blocks since your last real prompt; thinking/tool blocks, tool-result
  carriers, meta and sidechain entries skipped; 8-message/64KB caps),
  then swaps the full text into the reference. A candidate transcript
  is accepted **only if the visible truncated lines match the tail of
  its reconstructed reply**, so a concurrent session in the same cwd
  can never inflate the wrong conversation; no match → warn and leave
  the truncated reference as-is.
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
- **`vim.g.claude_reply_reinflate`** — set `false` to disable
  re-inflating a truncated reference from the session transcript
  (default: enabled).
- **`vim.g.claude_reply_transcript_dir`** — override the transcript
  directory searched for re-inflation (default: derived from
  `$CLAUDE_CONFIG_DIR` or `~/.claude`, plus the cwd slug). Mainly for
  tests and non-standard setups.

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

## Prior-reply picker (`\r`)

Back-search and re-use ANY earlier reply of the session, not just the
last one. **`\r`** (buffer-local; shadows the global vimrc-source map
only inside compose buffers) or `:ClaudeReplyPick` opens a fuzzy
picker over every prior turn — **telescope** when available (custom
picker: your own sorter/theme/mappings; the `ordinal` carries the
full reply text so fuzzing matches reply *content*, with a live
markdown preview pane), else a plain `vim.ui.select` fallback.

- **`<CR>` — "reference paging"**: swaps the chosen turn INTO the
  reference region, so the whole normal workflow (`]m`/`[m`, granular
  `\e` pulls, folds) applies to the older reply. The header line gets
  a `⟨#N/M⟩` tag (`⟨#M/M live⟩` when back on the newest); re-`\r` to
  page elsewhere.
- **`<C-q>` — quote whole turn**: short-circuit; appends the entire
  selected reply as a wrapped `> ` quote below the marker.

Turn sources per provider: claude — `all_replies()` over the session
jsonl (turn = consecutive assistant messages between real user
prompts; tool-result carriers/meta/sidechain noise skipped; the RIGHT
transcript is resolved once by tail-matching the visible reference,
then cached); opencode — `oc-last-reply.py --list` (same grouping,
from the sqlite store).

Caveat (same as roadmap #2): paging/quoting an older turn does NOT
rewind the conversation — whatever you compose is still sent as the
next message in the live session. It's "respond to something you
forgot", not time travel (that's Claude's own Esc-Esc rewind).

## Session picker (`\R`) — cross-harness

One level up from `\r`: **`\R`** (or `:ClaudeReplySessions`) fuzzes
over **sessions from BOTH harnesses' stores merged** — claude
(`~/.claude/projects/<slug>/*.jsonl`; title = last
`custom-title`/`ai-title` line, `last-prompt` fallback) and opencode
(sqlite `session` table via `oc-last-reply.py --sessions`) — rows like
`[oc] 07-03 20:38  taken_todo_sys  (repos/lns)`, preview = that
session's last reply (lazily fetched, cached). Scope defaults to the
cwd project; **`<C-a>`** toggles all-projects/all-dirs (claude side
capped to the newest 30 transcripts). `<CR>` drills into the normal
turn picker for that session (`<CR>` page / `<C-q>` quote as usual;
**`<C-o>`** goes back to the session list). Foreign-session pages tag
the header `⟨<session title> #N/M⟩` so you always know whose reply
you're reading. Since quoting is just text, this is **cross-harness
pollination**: quote a claude reply into an opencode conversation and
vice versa. Same `vim.ui.select` fallback when telescope is absent.

## opencode support

The plugin's second provider (opencode `1.17.9`, verified by
decompiling its bundle). Same UX — `]m`/`[m`, `\e` pulls, folds,
highlight — but the wiring is inverted because opencode's external
editor is much more bare-bones than Claude Code's:

- `editor_open` (default **ctrl+e**) writes ONLY the current prompt
  draft to **`<os.tmpdir()>/<Date.now()>.md`** (a 13-digit epoch-ms
  basename), spawns `$VISUAL || $EDITOR` blocking (TUI suspended,
  fn `ue` in the bundle), then reads the **whole file back** into the
  prompt box. No reference content, no marker stripping, no
  config-file editor setting.
- So the plugin does both sides itself, nvim-side only:
  1. an autocmd on `<tmpdir>/*.md` (basename must be exactly 13
     digits) **injects** the session's last assistant reply as plain-md
     reference above a reply marker (same `# ───…` shape as Claude's,
     so all shared machinery applies), keeping any in-progress draft
     below the marker;
  2. a **`BufWriteCmd`** strips everything at/above the marker on
     save — the `Vt_`-equivalent opencode lacks — so opencode receives
     only your quotes + reply.
- The last reply comes from **`oc-last-reply.py`** (stdlib-only):
  reads opencode's sqlite store read-only
  (`~/.local/share/opencode/opencode-stable.db`, `session`/`message`/
  `part` tables, ~20ms) for the most-recently-updated top-level
  session at/under nvim's cwd (opencode spawns the editor with
  cwd = worktree root). `--via-export` instead chains the built-in
  CLI (`opencode session list` + `opencode export <id>` — export must
  go to a file: its stdout truncates on pipes) — slower (~1.2s+) but
  schema-drift-proof; it's the documented fallback.
- Injected reference lines that would themselves parse as markers
  (a session *about* this plugin…) are defused with a `·` prefix.
- Zero opencode-side configuration: nvim already is the editor via
  `$EDITOR`. Knobs: `vim.g.claude_reply_opencode = false`
  (kill-switch), `claude_reply_python`, `claude_reply_oc_script`,
  `claude_reply_oc_via_export`, `claude_reply_oc_fetch_cmd`
  (full command override; used by tests).
- Save semantics: clearing everything below the marker **clears the
  prompt box** — the plugin writes a lone newline rather than a 0-byte
  file, because opencode treats an empty read-back as *abort*
  (`content || undefined` in fn `ue`) and would silently keep the old
  prompt; the newline reads back truthy and opencode's own
  trailing-newline strip reduces it to `""`. Trailing blank padding is
  trimmed on save (interior blanks kept).
- Caveats: no per-session identity check (heuristic = most recent
  session for cwd; two concurrent opencode sessions in one dir could
  cross-pollinate the *reference*, never the sent text); a bare `:q`
  aborts cleanly (buffer marked unmodified after injection, draft
  survives); deleting the marker line sends the whole buffer.

## Roadmap

Follow-up ideas (older-reply quoting, a transcript side-panel,
cross-provider profiles, a plenary test suite, proper lazy.nvim
packaging) are scoped with feasibility verdicts in
[`plans/claude/claude-reply-roadmap.md`](../../plans/claude/claude-reply-roadmap.md).
