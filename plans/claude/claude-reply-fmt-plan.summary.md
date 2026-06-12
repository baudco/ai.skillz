Add `claude-reply` nvim Ctrl-G quote-reply

Build an nvim integration that turns Claude Code's **Ctrl-G "edit last
response"** buffer into an email-style, quote-and-reply composer, plus
a reproducible package in `commands/claude-reply/`.

- decompile Claude Code `2.1.156` to verify the mechanism: Ctrl-G
  (`externalEditorContext` on) opens `claude-prompt-<uuid>.md` via
  `$VISUAL`/`$EDITOR`; `Tt_()` writes the last response as `# `-
  reference above a `Write your reply below this line` marker; on save
  `Vt_()` keeps only what is **below** the marker — there is **no
  hook** for this buffer, so nvim is the only lever.
- add `commands/claude-reply/claude-reply.lua` — a self-contained
  lazy.nvim spec (runs `setup_autocmds()` at import, returns `{}`)
  firing on `claude-prompt-*.md`: `]m`/`[m` jump between response
  sections, `\e` (normal + visual) pulls the section under the cursor
  down below the marker as a `gq`-wrapped (`textwidth=69`) `> `
  blockquote and drops into insert mode; reference is soft-wrapped and
  folded by section; no-ops when markers are absent.
- force a faithful `gq` via buffer-local `tw`/`fo`/`comments` (snapshot
  + restore, clear `formatexpr`/`formatprg`) so wrapping matches a
  manual `gqap` and preserves the `> ` leader.
- choose `\e` ("edit") to avoid the global `\q` `ListToggle` collision;
  all maps buffer-local via `<Plug>(ClaudeReplyPull)`.
- symlink the module into `~/repos/dotrc/dotrc/nvim/lua/plugins/`
  (→ `~/.config/nvim`); add `README.md` (verified mechanism + the
  debunked `prettier` `PostToolUse` suggestion) and `DEPLOY.md` (symlink
  + the one-time `/config` → "Show last response in external editor").
- verify headlessly: `-u NONE` logic checks (16/16), isolated
  `lazy.setup` load (2 autocmds, no error), and the **real** config
  (ft=markdown, folds, cursor park, `\e` map) — a real-config `\e`
  pull wraps a heading+bullets section to ≤69 cols preserving markdown
  list structure.

- re-inflate truncated references: Claude Code hard-caps the Ctrl-G
  reference at 50 lines (`rh4=50`, no setting); when the
  `… (earlier output truncated)` sentinel is present, reconstruct the
  full last reply from the session transcript
  (`~/.claude/projects/<cwd-slug>/*.jsonl`, mirroring the binary's
  `WG4` walk: skip thinking/tool blocks, tool-result/meta/sidechain
  entries, 8-msg/64KB caps) and swap it in — a candidate transcript is
  accepted only when the visible truncated lines tail-match its
  reconstruction, so concurrent same-cwd sessions can't cross-inflate;
  opt-out via `vim.g.claude_reply_reinflate`, dir override via
  `vim.g.claude_reply_transcript_dir`
- add DWIM pull granularity: `\e` on a bullet/numbered list item (any
  nesting depth) quotes just that item + its indented children —
  minimizing quoted tokens in the next send; heading/prose lines still
  pull the whole section; whole-section from an item via the heading
  or a V-select
- harden after live use: anchor marker detection on the `# ─` (U+2500)
  box rule so a response that *mentions* the marker phrase in prose no
  longer truncates the navigable region; de-hash the reference into
  plain markdown for native syntax highlighting (no re-inject — the
  send is bounded by the marker line); detach treesitter for the
  compose buffer and use builtin markdown syntax so a broken/absent
  markdown TS parser can't crash it; add opt-in
  `vim.g.claude_reply_colorscheme` (restored on buffer-leave) and
  `vim.g.claude_reply_highlight` (`syntax`/`treesitter`/`off`).

Remaining (manual, per-user): enable `externalEditorContext` via
`/config`. No restart needed — each Ctrl-G spawns a fresh nvim that
imports the spec. Out of scope: the transcript-view `v` →
`cc-transcript-*.txt` path.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
