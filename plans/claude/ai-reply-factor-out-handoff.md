# HANDOFF: factor `claude-reply` out into the standalone `ai.reply` plugin

**Audience: an agent with NO prior session context.** Everything you
need is in this document — read it fully before acting. This is a
PURE RESTRUCTURE: zero behavior change is the acceptance bar.

## House rules (non-negotiable)

- **NEVER run `git commit`/`push`/`amend`/`rebase` yourself.** Stage
  at most, write the commit-message artifact(s), and hand the human
  a `git commit --edit --file <artifact>` command. This applies in
  EVERY repo you touch.
- Wrap any commit-message prose you generate with
  `python3 ~/repos/ai.skillz/skills/pr-msg/scripts/rewrap.py --width 67`.
  Never hand-wrap.
- Write your plan/summary docs under `~/repos/ai.skillz/plans/claude/`
  (`<name>.md` + `<name>.summary.md` after execution).
- NixOS host: no system pip. `python3` is on PATH. Use `uv` if a venv
  is ever needed (it is NOT for this phase — the py file is
  stdlib-only).
- Verify with headless nvim after EVERY structural step (commands
  given below). If a step fails, fix before proceeding — do not stack
  broken steps.

## What this plugin is (context in one paragraph)

`claude-reply` is a single-file nvim plugin that augments the
external-editor "compose buffer" that two AI CLI harnesses open:
Claude Code (Ctrl-G → `claude-prompt-*.md`, needs its
`externalEditorContext` setting) and opencode (ctrl+e →
`<tmpdir>/<13-digit-epoch-ms>.md`). It shows the AI's last reply as a
markdown "reference region" above a `# ─── Write your reply below
this line ───` marker, and gives: section nav (`]m`/`[m`), quote-pull
(`\e` → `gq`-wrapped `> ` blockquote), a prior-turn picker (`\r`), a
cross-harness dialog/session picker (`\d`, telescope, grouped by
project), and deep paragraph-level content search (`<C-g>`,
`:ClaudeReplyGrep`). A companion stdlib-only python script
(`oc-last-reply.py`) reads opencode's sqlite store. Only text BELOW
the marker is ever sent back to the harness.

## Current state (verify before starting; commit `git log` may have
advanced)

- Source of truth: `~/repos/ai.skillz/commands/claude-reply/`
  - `claude-reply.lua` (~1944 lines, ONE file: lazy.nvim spec that
    does all work at import and returns `{}`)
  - `oc-last-reply.py` (~294 lines)
  - `README.md`, `DEPLOY.md`
- Deploy chain: `~/.config/nvim` → `~/repos/dotrc/dotrc/nvim`;
  `dotrc/nvim/lua/plugins/claude-reply.lua` is a SYMLINK to the
  ai.skillz lua file. lazy.nvim auto-imports every
  `lua/plugins/*.lua` (see `dotrc/nvim/lua/config/lazy.lua`).
- The lua registers itself as `package.loaded["claude_reply"]` and
  runs `M.setup_autocmds()` at import time.
- Naming DECISION (already made): plugin = **`ai.reply`**, repo =
  `~/repos/ai.reply` (LOCAL ONLY, no forge push), lua module =
  `require("ai.reply")` from `lua/ai/reply/init.lua`, python import
  path reserved as PEP 420 `ai.reply` (NOT needed this phase).
  Dots in repo/plugin names are fine — `mini.nvim`/`mini.*` precedent.
- Check `git -C ~/repos/ai.skillz status` first: if
  `commands/claude-reply/*` changes are uncommitted, STOP and ask the
  human to commit before you begin.

## Target layout

```
~/repos/ai.reply/
  lua/ai/reply/init.lua          setup(opts) + autocmds + hl defs + public API
  lua/ai/reply/config.lua        opts store, g:-var fallbacks, key/knob resolution
  lua/ai/reply/markers.lua       BOX/marker consts, find_markers, classify, dehash,
                                 set_reference, strip_reference
  lua/ai/reply/pull.lua          with_format_opts, pull_section, pull_under_cursor,
                                 pull_visual, nav_section, section/item bounds,
                                 foldexpr + apply_folds
  lua/ai/reply/view.lua          apply_view_opts, highlight (TS detach), colorscheme
  lua/ai/reply/providers/claude.lua    transcript_dir, list_transcripts,
                                 last_reply_text, all_replies, tail_matches,
                                 reinflate, resolve_transcript, claude_sessions
                                 (title/cwd harvest), setup_buffer
  lua/ai/reply/providers/opencode.lua  tmpfile detection, inject/setup_opencode_buffer,
                                 oc_write, opencode_last_reply, oc_json, script path
  lua/ai/reply/pickers.lua       caches, hl_display, badge_hl, map_clear_first_cc,
                                 fmt_ts/fmt_date/first_line/path_label/slug_label,
                                 fetch_turns, list_sessions, dialog_items,
                                 pick_reply, pick_session, explode_paras, deep_rows,
                                 pick_deep, grep_replies
  python/ai_reply_extract.py     oc-last-reply.py, renamed, content UNCHANGED
  plugin/ai-reply.lua            `if vim.g.loaded_ai_reply then return end` guard +
                                 require("ai.reply").setup()  (default wiring)
  doc/ai-reply.txt               help doc (generate from README; include tags)
  tests/minimal_init.lua + tests/*_spec.lua + Makefile   (plenary-busted)
  README.md  DEPLOY.md           moved + updated names
```

Use the section map of the monolith to guide the split — current
line anchors (approximate; re-grep before cutting):
buffer scan @53, nav @169, pull @224, folds @369, reinflate @391,
strip/view/highlight/colors @619-703, maps @705, setup_ui @777,
opencode provider @787, pickers @933-1862, setup/autocmds @1864-1944.

## Step-by-step

### 1. Seed the repo WITH history

```bash
cd ~/repos/ai.skillz
git subtree split -P commands/claude-reply -b ai-reply-split
mkdir ~/repos/ai.reply && cd ~/repos/ai.reply && git init
git pull ~/repos/ai.skillz ai-reply-split
git -C ~/repos/ai.skillz branch -D ai-reply-split   # after pull OK
```

Result: `~/repos/ai.reply` containing `claude-reply.lua`,
`oc-last-reply.py`, `README.md`, `DEPLOY.md` at root with full
history. All subsequent work happens in `~/repos/ai.reply`.

### 2. Mechanical moves FIRST (each its own commit-artifact unit)

a) `git mv oc-last-reply.py python/ai_reply_extract.py` and update
   the ONE reference in the lua (`plugin_dir() .. "/oc-last-reply.py"`
   → the new relative path; note `plugin_dir()` resolves the lua
   file's own realpath — after the split it must resolve the REPO
   root: rework it to
   `vim.fn.fnamemodify(<this-file's realpath>, ":h:h:h:h")` from
   `lua/ai/reply/providers/opencode.lua` — VERIFY with a print).
b) Move the monolith to `lua/ai/reply/init.lua` unchanged; add
   `lua/ai/reply/` path. Verify it still loads (headless command in
   §Verification) BEFORE splitting further.

### 3. Split into modules

- Cut top-down following the section map; each extracted module
  returns its own table; `init.lua` requires them and re-exports the
  public fns so `require("ai.reply").<fn>` keeps working:
  `find_markers, set_reference, nav_section, pull_section,
  pull_under_cursor, pull_visual, with_format_opts, foldexpr,
  last_reply_text, all_replies, opencode_last_reply, list_sessions,
  pick_reply, pick_session, pick_deep, grep_replies, setup_buffer,
  setup_opencode_buffer, setup_autocmds, define_hls`.
- Locals shared across modules (e.g. `warn`, `BOX`, `is_marker`,
  `path_label`, caches) move to the module that owns them and get
  exported/required explicitly. NO globals.

### 4. `setup(opts)` + compat

`require("ai.reply").setup({...})` with this exact opts table
(defaults in parens); each falls back to the LEGACY `vim.g.
claude_reply_*` var when the opt is nil — keep that fallback for one
release:

| opts key            | legacy g: var                     | default |
| ------------------- | --------------------------------- | ------- |
| keys.pull           | claude_reply_key_pull             | `<leader>e` |
| keys.replies        | claude_reply_key_replies          | `<leader>r` |
| keys.dialogs        | claude_reply_key_dialogs          | `<leader>d` |
| highlight           | claude_reply_highlight            | "syntax" |
| colorscheme         | claude_reply_colorscheme          | nil |
| grepper             | claude_reply_grepper              | rg-if-executable else grep |
| python              | claude_reply_python               | exepath("python3") |
| opencode            | claude_reply_opencode             | true |
| dialogs_grouped     | claude_reply_dialogs_grouped      | true |
| reinflate           | claude_reply_reinflate            | true |
| transcript_dir      | claude_reply_transcript_dir       | nil (auto) |
| oc_script           | claude_reply_oc_script            | nil (auto) |
| oc_via_export       | claude_reply_oc_via_export        | false |

Test hooks stay g:-only (used by the test suite):
`claude_reply_oc_{fetch,list,sessions,dump}_cmd`. Add matching
`ai_reply_oc_*_cmd` names that take precedence.

Renames WITH aliases (old names must keep working):
- `package.loaded["ai.reply"]` is the module; ALSO set
  `package.loaded["claude_reply"] = <same table>` (the foldexpr
  string `v:lua.require'claude_reply'.foldexpr(v:lnum)` in old
  sessions + any user config depends on it). Change the foldexpr
  string to `v:lua.require'ai.reply'.foldexpr(v:lnum)`.
- Commands: new `:AiReplyPick`, `:AiReplyDialogs`, `:AiReplyGrep`
  (+ keep `:ClaudeReplyPick`, `:ClaudeReplyDialogs`,
  `:ClaudeReplySessions`, `:ClaudeReplyGrep` as aliases).
- `<Plug>(ClaudeReplyPull)` → add `<Plug>(AiReplyPull)`, keep old.
- Highlight groups: new `AiReplyCc/Oc/Date/Proj` defined as before;
  define old `ClaudeReplyCc/…` as links to the new ones.
- Buffer vars (`b:claude_reply_ready`, `b:claude_reply_provider`,
  `b:claude_reply_lo/hi`, `b:claude_reply_transcript`): KEEP the
  names this phase (internal; renaming buys nothing and risks the
  reassert path).

CRITICAL packaging change: the file currently RUNS
`setup_autocmds()` at import (lazy `plugins/*.lua` side-effect
pattern). As a real plugin that moves to `plugin/ai-reply.lua`
(guarded `setup()`), and `setup(opts)` must be idempotent
(re-callable; augroup uses `clear = true` already).

### 5. Port the test suite to plenary-busted

plenary.nvim is installed at `~/.local/share/nvim/lazy/plenary.nvim`.
`tests/minimal_init.lua`: prepend plenary + this repo to rtp,
`require("ai.reply").setup()`. Makefile target:

```
nvim --headless --noplugin -u tests/minimal_init.lua \
  -c "PlenaryBustedDirectory tests/ {minimal_init='tests/minimal_init.lua'}"
```

Write these spec files; the assertions to port are the ad-hoc
harnesses developed in the origin session — recreate them from the
described behaviors (each was verified green):

- `markers_spec.lua`: `# ─`-anchored marker detection (a reference
  line merely MENTIONING "Write your reply below this line" in prose
  must NOT match — the anchor is `^# ` + U+2500, bytes
  `\226\148\128`); exactly-one-reply-marker invariants.
- `dehash_spec.lua`: `# x`→`x`, `#`→``, `# ## h`→`## h`; reference
  de-hash leaves marker lines verbatim; buffer marked unmodified.
- `pull_spec.lua`: `\e` pull → `> `-quoted, `gq`-wrapped ≤69 cols
  (buffer-local tw=69 forced), DWIM list-item pull, visual pull,
  blank-edge trimming; interior blanks preserved on save.
- `claude_spec.lua`: fixture jsonl parsing — **fixtures MUST be
  compact JSON** (`json.dumps(..., separators=(",", ":"))`) because
  the line prefilter matches `"type":"assistant"` without spaces;
  `all_replies` turn grouping (tool_result carriers do NOT close a
  turn; `isMeta`/`isSidechain` skipped); re-inflation tail-match;
  title harvest last-`customTitle`/`aiTitle` wins, `lastPrompt`
  fallback; cwd harvest via `grep -m1` → `path_label` (dots/dashes
  survive), slug fallback lossy.
- `opencode_spec.lua`: 13-digit-epoch basename gating under $TMPDIR
  (set TMPDIR for the test nvim!); inject w/ draft-below-marker;
  middot-defusal of marker-shaped lines in fetched replies;
  `oc_write`: strips at/above marker, drops leading blanks, trims
  trailing blank padding, writes binary-mode 'b' (NO trailing
  newline — opencode's `le()` only strips single-line trailing NLs)
  EXCEPT the cleared case which writes exactly one `\n` (a 0-byte
  file means "abort" to opencode and would keep the old prompt).
- `pickers_spec.lua` (fallback paths — telescope absent under
  --noplugin): pick_reply/pick_session/pick_deep via stubbed
  `vim.ui.select`; session merge order across sec-vs-ms timestamps;
  45s TTL caches (break the stub cmd after priming → still served);
  grouped dialog_items (headers absent from fallback); `⟦<real pwd
  label>⟧` (never the literal "pwd"); header ⟨#N/M⟩/⟨title #N/M⟩
  tags (strip pattern `%s*⟨[^⟩]*⟩%s*$`).
- `deep_spec.lua`: paragraph explosion (one row per para; para-level
  pat filter); **ordinal ≤ ~900 chars** (fzf-native only matches
  ~the first 1KB of an item — whole-turn ordinals silently break
  content matching; this was a real prod bug, do not regress);
  `<C-q>`-quotes-the-para vs `<CR>`-pages-the-turn contract;
  py `--dump`/`--grep`/`--sessions`/`--session` against a fixture
  sqlite db (schema: session/message/part; message.data JSON has
  `role`; part.data JSON has `type`/`text`; child sessions have
  parent_id and are excluded; NB the extractor `fetchall()`s outer
  rows — a streamed cursor gets clobbered by inner queries).

### 6. Flip the deploys

a) dotrc: DELETE the symlink
   `dotrc/nvim/lua/plugins/claude-reply.lua`; CREATE
   `dotrc/nvim/lua/plugins/ai-reply.lua` containing:
   ```lua
   return {
     dir = vim.fn.expand("~/repos/ai.reply"),
     name = "ai.reply",
     lazy = false,
     opts = {},
   }
   ```
   (lazy.nvim calls `require("ai.reply").setup(opts)` automatically
   when `opts` is present ONLY with `main` resolvable — set
   `main = "ai.reply"` explicitly to be safe.)
b) ai.skillz: replace `commands/claude-reply/` contents with a short
   `README.md` pointing at `~/repos/ai.reply` (keep git history;
   plan docs under `plans/claude/` stay).
c) Stage both repos, write commit artifacts (rewrap 67), give the
   human the commit commands. THREE repos are touched overall:
   ai.reply (new), dotrc, ai.skillz.

## Landmine index (learned the hard way — respect each)

1. `BOX = "\226\148\128"` (U+2500) — markers are matched by
   `^# ` .. BOX prefix + phrase. LuaJIT has no `\u{}` escapes.
2. Compose buffers must NO-OP when no reply marker exists
   (`externalEditorContext` off / random md files).
3. Claude buffers must NEVER get the opencode `BufWriteCmd` (claude
   strips server-side; opencode needs our strip).
4. Treesitter is DETACHED per-buffer by default (`highlight =
   "syntax"`): a broken md TS setup crashes redraw otherwise. Keep
   the deferred second `apply_highlight` pass (FileType races).
5. All picker→picker hops MUST be `vim.schedule()`d (same-tick
   close/reopen leaks the trigger key into the new prompt).
6. Queries carried between pickers get `%c`-stripped at entry.
7. `with_format_opts` snapshots/restores buffer-local
   tw/fo/comments/formatexpr/formatprg — the ONLY way `gq` output
   matches the user's manual `gq`. Do not "simplify".
8. opencode tmpdir detection: `(vim.uv or vim.loop).os_tmpdir()` at
   AUTOCMD-REGISTRATION time in the spawned nvim (it inherits the
   harness env). Autocmd `*` crosses `/` — keep the strict 13-digit
   basename gate.
9. `grep` harvests: titles want the LAST match per file; `"cwd"`
   MUST use `-m1` (every jsonl line contains it — full scan explodes).
10. Fixture jsonl must be COMPACT json (see claude_spec above).
11. `vim.g` test-hook cmds are LISTS (`{'cat', 'file'}`), not
    strings.
12. The `plugin_dir()`/script-path resolution goes through the OLD
    deploy symlink today (`fs_realpath`); after the flip there is no
    symlink — the relative `python/` path must work from the repo
    layout AND still honor `oc_script`/`g:claude_reply_oc_script`.
13. Do NOT touch `~/repos/dotrc`'s unrelated dirty files; stage ONLY
    the plugin spec change there.
14. `nvim -u NONE` + `dofile(...)` no longer works post-split (module
    requires); all verification goes through `tests/minimal_init.lua`
    or the real config.

## Verification (run all; paste outputs in your summary)

```bash
# 1. plenary suite
cd ~/repos/ai.reply && make test          # expect 0 failures

# 2. real-config load + claude-path smoke
cat > /tmp/claude-prompt-VERIFY.md <<'EOF'
# ─── Claude's last response (for reference; removed on save) ───
# A paragraph long enough to exceed the sixty-nine column width so gq wraps it.
# ─── Write your reply below this line ──────────────────────────

EOF
nvim --headless -c "edit /tmp/claude-prompt-VERIFY.md" \
  -c "lua local M=require('ai.reply'); local mk=M.find_markers(0); vim.api.nvim_win_set_cursor(0,{2,0}); M.pull_under_cursor(0); vim.cmd('stopinsert'); local A=vim.api.nvim_buf_get_lines(0,0,-1,false); local q=0; for _,l in ipairs(A) do if l:match('^> ') then q=q+1 end end; print('OK='..tostring(mk.reply==3 and q>=2))" -c "qa!"

# 3. opencode-path smoke (real store; run from a project with an oc session)
cd ~/repos/lns && export TMPDIR=/tmp/vfy && mkdir -p $TMPDIR
F="$TMPDIR/$(date +%s%3N).md"; printf 'draft\n' > "$F"
nvim --headless -c "edit $F" -c "lua vim.wait(400); print('PROVIDER='..tostring(vim.b[0].claude_reply_provider))" -c "write" -c "qa!"
cat "$F"   # expect: only 'draft' (reference stripped)

# 4. compat: old command + old g: var + old <Plug> still work
nvim --headless -c "edit /tmp/claude-prompt-VERIFY.md" \
  -c "lua print('CMD='..tostring(vim.fn.exists(':ClaudeReplyGrep')==2)..' MOD='..tostring(package.loaded['claude_reply']~=nil))" -c "qa!"
```

Also do ONE live interactive check with the human: fresh harness
ctrl+e/ctrl+g → `\e`, `\r`, `\d`, `<C-g>`, `:AiReplyGrep foo`.

## Deliverables

1. `~/repos/ai.reply` — split, tested, with README/DEPLOY updated to
   the new names (keep the decompiled-mechanism docs intact — they
   are the plugin's institutional knowledge).
2. dotrc + ai.skillz deploy flips (staged, not committed).
3. Commit-msg artifacts per repo (`.claude/git_commit_msg_LATEST.md`
   convention in ai.skillz; plain artifact files elsewhere is fine).
4. `~/repos/ai.skillz/plans/claude/ai-reply-factor-out.summary.md`
   describing what was done (git-commit-msg style, wrapped at 69).
5. An updated line in `plans/claude/ai-reply-followup-plan.md`
   marking Phase 1 done.

## Explicitly OUT of scope

- ANY behavior change, however tempting (log them in the summary as
  follow-ups instead).
- The python daemon (`py-extension-plan.md`) — Phase 2, different
  session, blocked on a user brain-dump.
- Publishing the repo to a forge; CI.
- Renaming buffer-local `b:claude_reply_*` vars.
