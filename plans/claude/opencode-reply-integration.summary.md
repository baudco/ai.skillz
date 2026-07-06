Add `opencode` provider to `claude-reply` nvim plugin

Extend the Ctrl-G quote-reply plugin to work identically inside
`opencode` (1.17.9) — same nvim UX (`]m`/`[m` nav, `\e` pulls,
folds, highlight), new provider wiring; zero opencode-side config.

- decompile the opencode bundle to verify `editor_open` (ctrl+e)
  mechanics (fn `ue`): prompt draft written to
  `<os.tmpdir()>/<Date.now()>.md`, `$VISUAL||$EDITOR` spawned
  blocking, WHOLE file read back into the prompt box — no reference
  content, no marker strip, no config-file editor setting.
- add `commands/claude-reply/oc-last-reply.py` (stdlib-only): fetch
  the last assistant reply for the most-recently-updated top-level
  session at/under cwd from opencode's sqlite store (`session`/
  `message`/`part` tables, read-only, ~20ms); `--via-export` chains
  the built-in CLI (`session list` + `export <id>` — export stdout
  truncates on pipes, must redirect to a file) as the
  schema-drift-proof fallback (~1.2s+).
- wire the provider in `claude-reply.lua`:
  - autocmd on `<tmpdir>/*.md` gated on an exactly-13-digit basename
    (opencode's epoch-ms name, constant until 2286); nvim inherits
    opencode's `$TMPDIR` so `os_tmpdir()` matches;
  - inject the fetched reply as PLAIN-markdown reference between
    Claude-shaped `# ───…` markers (all shared machinery applies),
    keep any in-progress draft below the marker, mark the buffer
    unmodified (bare `:q` aborts clean);
  - defuse marker-shaped lines inside the fetched reply with a `·`
    prefix (find_markers hijack guard);
  - `BufWriteCmd` writes ONLY below-marker content to disk — the
    `Vt_`-strip opencode lacks; a cleared reply area writes a lone
    newline (never 0 bytes: opencode treats an empty read-back as
    abort and would keep the old prompt — the newline reads back
    truthy and opencode's own trailing-newline strip yields `""`,
    genuinely clearing the prompt box); trailing blank padding
    trimmed, interior blanks kept;
  - genericize `HEAD_TXT` to "last response" and extract shared
    `setup_ui`/`reassert_view` (the seam for roadmap #3's profile
    registry).
- knobs: `vim.g.claude_reply_opencode=false` kill-switch,
  `claude_reply_python`, `claude_reply_oc_script`,
  `claude_reply_oc_via_export`, `claude_reply_oc_fetch_cmd` (test
  stub).
- verify headless: 19/19 opencode-flow checks (inject, sanitize,
  draft-below-marker, nav, pull, on-write strip, 13-digit gating),
  8/8 claude regression (incl. no `BufWriteCmd` leak), plus a
  real-config + real-DB end-to-end (lns session reply injected,
  `:w` leaves only the draft on disk).
- docs: README "opencode support" section, DEPLOY opencode section
  (requirements + optional ctrl+g rebind), roadmap #3 status note.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
