# `ai.reply` — ultra-detailed follow-up plan (session 2026-07-06/07)

The consolidated, ordered TODO backlog from this session. Each phase
has concrete steps, file targets, verification, and open decision
points. Companion docs: `standalone-plugin-plan.md` (naming/layout —
DECIDED: `ai.reply`, `~/repos/ai.reply`, `lua/ai/reply/`),
`py-extension-plan.md` (daemon + remote), `claude-reply-roadmap.md`
(historical feature log).

---

## Phase 0 — land the in-flight hotfix (immediate)

The working tree holds one uncommitted `claude-reply.lua` change-set:
- proj labels from real jsonl `"cwd"` (slug mangling fix) +
  `path_label`/`slug_label` split + `-m1` cwd harvest,
- deep-search **paragraph corpus** (fzf-native ~1KB match-window fix;
  `explode_paras`, para-level `pat` filter, `<C-q>` quotes the
  passage, `<CR>` pages the turn),
- `<C-g>` from the turn picker too; query `%c`-sanitization at
  picker entry points; `⟦proj⟧` prefix on drilled-in turn-picker
  titles; deep rows carry `(proj)`.

Steps: `git add commands/claude-reply/claude-reply.lua` (+ the README
deep-search edit) → `git commit --edit --file
.claude/git_commit_msg_LATEST.md`.

Verify after commit: fresh `ctrl+e` → `\d` → `<C-g>` → type a phrase
you remember from an OLD reply's body → rows narrow to passages (the
live harness showed 162 → 44 rows on "footer contract").

**Watchlist item**: the transient `G` flash in the OLD prompt during
the `<C-g>` handoff (cosmetic; the query sanitizer stops it
propagating). If it still bothers: investigate feedkeys flush
(`vim.fn.feedkeys("", "x")`) inside the transition, or an upstream
telescope issue search. LOW priority.

---

## Phase 1 — execute the `ai.reply` factor-out

> **HANDOFF-READY**: the full self-contained brief for another agent
> is `plans/claude/ai-reply-factor-out-handoff.md` — house rules,
> current-state inventory, module split table, setup(opts)+compat
> spec, plenary port spec-by-spec, deploy flips, a 14-item landmine
> index, verification commands, deliverables. An agent should need
> ONLY that doc. The outline below is the short form.

Pure restructure, NO behavior change. Do in a worktree/branch.

1. **Create the repo**: `git init ~/repos/ai.reply` (local-only per
   decision). Seed history: `git -C ~/repos/ai.skillz subtree split
   -P commands/claude-reply -b ai-reply-split` → fetch that branch
   into the new repo as trunk (preserves the whole commit trail).
2. **Split the 1.8k-line monolith** into modules:
   - `lua/ai/reply/init.lua` — `setup(opts)`, autocmds, hl defs,
     public API re-exports (thin).
   - `lua/ai/reply/markers.lua` — BOX/marker constants, find/classify,
     de-hash, `set_reference`.
   - `lua/ai/reply/providers/claude.lua` — reinflate, transcript
     dir/list/parse (`all_replies`, `last_reply_text`), cwd/title
     harvest.
   - `lua/ai/reply/providers/opencode.lua` — tmpfile detect, inject,
     `oc_write`, extractor invocation (`oc_json`).
   - `lua/ai/reply/pull.lua` — `gq` machinery, `pull_section`, DWIM
     item bounds, nav.
   - `lua/ai/reply/pickers.lua` — turn/dialog/deep pickers, caches,
     hl_display, clear-first-cc.
   - `python/ai_reply_extract.py` — `oc-last-reply.py` renamed
     (stays stdlib-only single-file until the daemon).
   - `plugin/ai-reply.lua` — guarded default `setup()`.
3. **Config surface**: `setup({ keys = {pull, replies, dialogs},
   highlight, colorscheme, grepper, python, opencode = bool,
   dialogs_grouped = bool, transcript_dir, ... })`; keep reading
   `g:claude_reply_*` as fallbacks + `package.loaded["claude_reply"]`
   alias for ONE release; rename cmds `:AiReply{Pick,Dialogs,Grep}`
   (old names aliased).
4. **Port the ad-hoc headless suites to plenary-busted** (roadmap #4):
   `tests/{markers,dehash,sections,pull,highlight,opencode,pickers,
   sessions,deep}_spec.lua` + `tests/minimal_init.lua` + `Makefile`
   (`make test` = `nvim --headless --noplugin -u tests/minimal_init.lua
   -c "PlenaryBustedDirectory tests/ …"`). The assertions already
   exist in this session's transcript harnesses — mechanical port.
5. **Flip deploys**: dotrc lazy spec `{ dir = "~/repos/ai.reply",
   opts = {...} }` replacing the symlink; ai.skillz
   `commands/claude-reply/` becomes a pointer README (+ keep plan
   docs). Update dotrc + ai.skillz commits separately.
6. **Verify**: `make test` green; live ctrl+e/ctrl+g smoke in both
   harnesses; `:checkhealth lazy` clean; old `g:` vars still honored.

Effort: ~1 session. Risk: low (tests port first, then split).

---

## Phase 2 — py daemon (`ai.reply` py-pkg) — BLOCKED on brain-dump

Design doc: `py-extension-plan.md`. Locked requirements: decoupled
proc, RPC-only, location-transparent (remote-host via TCP/forwarded
socket; nvim `--listen`/`--server`, nvr), modden-wks spawned, prefer
anyio/trio-native minimal msgpack-rpc client (none exists on PyPI —
write ~200-line `ai.reply.rpc`), NOT the pynvim rplugin host
(deprecated direction upstream, neovim/neovim#27949).

**Await the user's remaining brain-dump**, esp.:
1. scope of what moves to py (indexing only vs interactive feats),
2. daemon lifecycle (modden wks service vs per-nvim child vs socket
   activation), 3. gish's exact role, 4. tractor actor-tree or plain
   trio, 5. packaging (`uv` + py313 venv convention; PEP 420
   `ai.reply` namespace).

Daemon endgame folds in several open papercuts:
- replaces the interim 45s TTL caches (warm cross-store index →
  instant `\d`/`<C-o>`/previews),
- unifies grep semantics (currently regex for rg on claude files vs
  plain substring in py for opencode — daemon owns ONE query lang),
- exact current-session identity via `~/.claude/sessions/<pid>.json`
  (live pid→session map; ancestor-pid walk from the compose nvim)
  instead of mtime/tail-match heuristics,
- opencode: consider watching the sqlite WAL or the event bus for
  live updates.

---

## Phase 3 — roadmap leftovers (post factor-out)

- **#1 transcript side-panel**: on compose-buffer open, optional
  vsplit rendering recent conversation (shared session reader). Truly
  live only via daemon/tmux (parent harness is frozen during the
  editor for claude; opencode TUI suspended). Design in roadmap doc.
- **#3 provider-profile registry**: formalize
  `providers/{claude,opencode}.lua` behind a
  `{detect, inject?, strip_on_save?, sessions, turns}` interface;
  document how to add gemini/codex etc. when their editor flows
  become interceptable.
- **Deep-picker polish candidates** (from live usage, pick per
  appetite): preview auto-scroll to + highlight of the matched
  paragraph; corpus caching keyed by scope (currently rebuilt per
  `<C-g>`; TTL like the others); para-row cap/stream for huge ⟦ALL⟧
  scopes; `:AiReplyGrep` regex passthrough flag (`-e`?) once daemon
  unifies semantics.

---

## Phase 4 — hygiene / stretch

- fzf-native ~1KB match-window: consider filing/linking an upstream
  issue (telescope-fzf-native) documenting the degenerate-score
  behavior we verified; local paragraph-corpus works around it.
- `keybindings.json`: claude-code `ctrl+e` rebind is per-user file —
  consider committing a copy under dotrc for provisioning.
- plenary CI (GitHub Actions) once/if `ai.reply` goes public.
- session-length: `/effort`-high test matrices are ad-hoc scripts in
  the transcript — the plenary port (Phase 1.4) is their durable home.

## Suggested execution order

Phase 0 now → Phase 1 next session (single focused block) →
brain-dump conversation → Phase 2 (daemon MVP: sessions/turns/grep
RPCs + lua client swap) → Phase 3 features on the new base.
