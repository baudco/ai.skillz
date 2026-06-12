# claude-reply — follow-up roadmap

Spitball research + plans for five proposed enhancements. **Nothing
here is built yet** — this is a scoped backlog with feasibility
verdicts and the facts that decide them (verified against Claude Code
`2.1.156` + the live nvim/dotrc setup, June 2026).

Suggested order: **#4 tests** and **#5 packaging** first (they make
everything after safer/shareable), then **#2 older-reply** (high value,
self-contained), then **#1 transcript panel** (shares infra with #2),
then **#3 cross-provider** (largest, most speculative).

---

## Shared infrastructure: a session-transcript reader

> **STATUS: partially built.** The reader's core now exists in
> `claude-reply.lua` (`M.last_reply_text`, `transcript_dir`,
> `list_transcripts`), added for the **truncation re-inflation**
> feature (Claude caps the Ctrl-G reference at 50 lines; the plugin
> reconstructs the full last reply from the transcript, validated by
> tail-match against the visible truncated lines). #1/#2 below extend
> this from "last reply" to "any turn" — move it to `session.lua` when
> #5's restructure happens.

#1 and #2 both need to read the live session transcript, so build this
once as `lua/claude-reply/session.lua`:

- **Locate the session JSONL.** Claude stores it at
  `~/.claude/projects/<slug>/<session-uuid>.jsonl`, where `<slug>` is
  the project cwd with `/`→`-` (e.g. `-home-goodboy-repos-ai-skillz`).
  The Ctrl-G nvim inherits Claude's cwd, so derive the slug from
  `vim.fn.getcwd()`; pick the **most-recently-modified** `*.jsonl` in
  that dir as the current session. (Claude exposes many `CLAUDE_*` env
  vars to the inherited editor env — worth probing `vim.env` at runtime
  for a session-id hint, but cwd+mtime is a robust fallback.)
- **Parse turns.** Each line is a JSON object; assistant turns are
  `{type:"assistant", message:{content:[ {type:"text",text} | {type:"thinking"} | {type:"tool_use"} ]}}`.
  Extract the `text` blocks (skip `thinking`/`tool_use`); group
  consecutive assistant lines since the previous `user` line into one
  logical "reply" (this mirrors Claude's own `WG4` context builder).
- Returns an ordered list of `{ index, role, text, timestamp }` we can
  drive a picker or panel from.

---

## #2 — Ctrl-G / quote from an OLDER reply  ·  ✅ very feasible

**Verdict:** doable entirely plugin-side; **no Claude cooperation
needed** because the transcript is on disk. High value, well scoped.

**Draft implementation design** (captured 2026-06-12; infra is ~70%
built — the re-inflation feature shipped `M.last_reply_text()` +
`transcript_dir()` + `list_transcripts()` with tail-match session
validation):

1. **`M.all_replies(path)`** — sibling of `last_reply_text()`. Same
   forward scan and entry classification (skip thinking/tool_use
   blocks, tool_result carriers, `isMeta`, `isSidechain`), but instead
   of *resetting* the accumulator on each real user prompt, it
   **closes the current turn and starts a new one**, returning an
   ordered list:
   `{ { text, first_line, ts = <timestamp of first entry> }, … }`.
   Reuse the per-message trim + `\n\n` join; no 8-msg/64KB cap (these
   are single turns). The current session file is chosen the same way
   re-inflation does (slug dir, mtime order); since the parent Claude
   process is frozen mid-Ctrl-G, the active session is the
   most-recently-written file — and for the picker the tail-match
   validation can also anchor on the *current* reference text.
2. **Picker UI** — buffer-local `\E` (capital; lowercase `\e` = pull)
   and `:ClaudeReplyPick`. Use `vim.ui.select` with labels like
   `[#7 12:31] Confirmed working live — excellent. Both asks…` (turn
   index + HH:MM + first ~60 cols of the first non-blank line).
   `vim.ui.select` automatically upgrades to telescope/fzf-lua/dressing
   if the user has one configured — no hard dependency.
3. **On pick** — two insertion modes:
   - default: run the chosen turn through the existing
     section/`gq`/`> `-quote machinery (`pull_section`) below the
     marker — quote the *whole* turn;
   - refine (v2): instead of quoting the whole turn, *swap the chosen
     turn into the reference region* (re-using the re-inflation swap +
     re-find-markers dance) so the normal `]m`/`[m` + granular `\e`
     workflow applies to the older turn — then a second `\E` (or a
     dedicated map) restores the live last-reply reference. This
     "reference paging" is the better UX and reuses everything.
4. **Caveat to surface in docs/UI**: quoting an older turn doesn't
   rewind the conversation — the composed text is still sent as the
   next message in the live session (rewind = Claude's own Esc-Esc
   checkpoint menu). Frame as "respond to something you forgot".
5. **Tests**: fixture jsonl with 3+ turns (interleaved tool_results,
   meta, sidechain noise) → `all_replies()` returns exactly the 3
   turns in order; picker insertion reuses the existing pull asserts;
   reference-paging swap preserves the reply-marker contract (exactly
   one marker, below-marker content untouched).

**Honest caveat to document:** this lets you *quote* an older message
for context, but your reply is still delivered to the **current** turn
(Claude's `Vt_` sends whatever is below the marker to the live prompt).
It does NOT rewind the conversation — for that the user wants Claude's
own Esc-Esc checkpoint/rewind. Framing: "quote anything from earlier;
it's sent as part of your current reply."

**Effort:** medium. **Risk:** low (read-only of JSONL; reuses pull
machinery). Reuses §shared reader.

---

## #1 — live parent-console view while editing  ·  ⚠️ partial

**Hard fact:** the input editor is spawned with **blocking
`spawnSync(editor, [file], {stdio:"inherit"})`** (`OF()` in the binary).
The Claude process is *synchronously frozen* for the entire Ctrl-G
session — its event loop doesn't run, streaming pauses, the TUI is
suspended. So a **truly "live" mirror is impossible in-process**: there
is no ongoing parent activity to show while you edit.

**What IS achievable:**
- **Read-only transcript side-panel.** On Ctrl-G, open a vertical split
  rendering the recent conversation (shared reader). It's a *snapshot*
  (the parent is frozen, so it won't tick), but it gives full
  scrollback/context while composing — which is most of the actual
  value. Cheap, no IPC.
- **Background-task tail (niche).** Background bash/agents/workflows run
  as separate processes writing to files under the Claude dirs; a split
  could `tail -f` a chosen task's output. Only useful if such a task is
  running; low priority.

**Route to genuine live (out of plugin core):** run Claude inside
**tmux**; have Ctrl-G open nvim in a tmux popup/split so the Claude
pane stays visible, or have the plugin detect `$TMUX` and mirror the
Claude pane via `tmux capture-pane`. This is a workflow/multiplexer
concern more than a plugin one — document as a recommended setup, maybe
ship a small tmux-aware helper.

**Effort:** panel = low-medium; true-live = a workflow doc. **Risk:**
low. Depends on §shared reader.

---

## #3 — cross-provider support  ·  🔭 design now, populate later

**Findings (web, June 2026):** the "compose your reply in `$EDITOR`
with the prior response quoted/marked" pattern is **fairly
Claude-specific**. Gemini CLI and Codex CLI expose "modify with
external editor" but for **diffs/patches**, not message composition,
and Gemini hard-codes an editor list (no `$EDITOR` until a pending
request lands). So there is no uniform cross-provider format to target.

**Approach — a provider-profile registry.** The plugin core (de-hash,
section model, `gq`-quote, nav, highlight) is already
provider-agnostic. Factor the provider-specific bits into a profile:
```
{ name, filename_glob, detect(buf) -> { header, reply, ref_region },
  reply_is_below_marker = true/false, ... }
```
Claude becomes the first profile (`claude-prompt-*.md`, the `# ─── …`
markers, `Vt_` below-marker send-contract). Adding a provider =
reverse-engineering its temp-file convention (same decompile/inspect
method used for Claude) and writing one profile table. Accept that some
providers (diff-editors) need a *different mode* entirely, not just a
profile — gate features per profile capability.

**Effort:** small to abstract; per-provider cost is the
reverse-engineering. **Risk:** medium (unknowns per tool). Do AFTER the
plugin is packaged (#5) so profiles live in a clean structure.

---

## #4 — native nvim test suite  ·  ✅ ready to go

**Verdict:** `plenary.nvim` is **already installed** → use
**plenary-busted**, the de-facto standard. (Alternative: `mini.test`,
better for screenshot/child-process tests — overkill here.)

**Structure:**
```
commands/claude-reply/
  lua/claude-reply/…           (after #5 restructure)
  tests/
    minimal_init.lua           (rtp += plugin + plenary; load module)
    markers_spec.lua           (find_markers: box-anchored, prose-mention immunity)
    dehash_spec.lua            (strip_reference -> plain md; markers verbatim)
    sections_spec.lua          (nav ]m/[m; section_bounds_at; headings split)
    pull_spec.lua              (\e -> > -quote, gq wrap <=69, contract intact)
    highlight_spec.lua         (TS detached; legacy syntax; no-op when no marker)
  Makefile                     (`make test`)
```
Run: `nvim --headless --noplugin -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/ {minimal_init='tests/minimal_init.lua'}"`.
The ad-hoc headless checks already written (12 de-hash, 9 end-to-end,
marker-precision, lazy-load) port directly to `describe/it` blocks — we
already have the assertions, just reshape them. Add a GitHub Actions
job once #5 gives it a repo.

**Effort:** low-medium (mechanical port). **Risk:** low.

---

## #5 — proper lazy.nvim package  ·  ✅ clear path

**Today:** one `claude-reply.lua` symlinked into `lua/plugins/`, doing
work as an import side-effect and `return {}`. That's a config hack,
not a distributable plugin.

**Target — standard plugin layout** (its own git repo, e.g.
`goodboy/claude-reply.nvim`):
```
claude-reply.nvim/
  lua/claude-reply/init.lua    (M + `setup(opts)`; opts replace vim.g.*)
  lua/claude-reply/session.lua (shared reader, §above)
  plugin/claude-reply.lua      (guarded: require('claude-reply').setup() default)
  doc/claude-reply.txt         (`:help claude-reply`, with tags)
  tests/ … (#4)
  README.md  LICENSE
```
- Convert `vim.g.claude_reply_*` → `setup({ colorscheme, highlight,
  keys, … })` (idiomatic; keep `vim.g` as fallback for one release).
- Lazy spec for users:
  ```lua
  { "goodboy/claude-reply.nvim",
    ft = "markdown",                       -- or event = "BufReadPre claude-prompt-*.md"
    opts = { highlight = "syntax", colorscheme = "rasmus" } }
  ```
  Lazy-load on the `claude-prompt-*.md` pattern so it costs nothing
  otherwise.
- **Migration:** keep canonical source in `ai.skillz/commands/claude-reply/`
  and publish via `git subtree split` to the standalone repo (or invert:
  develop in the plugin repo, vendor a copy/submodule back into
  ai.skillz). Either keeps one source of truth.

**Effort:** medium. **Risk:** low. Unblocks #3 (clean profile dir) and
#4 (repo for CI).

---

## Dependency graph

```
#5 packaging ──┬──> #4 tests (repo + clean lua/ structure)
               └──> #3 cross-provider (provider-profile dir)
session reader ──┬──> #2 older-reply  (picker over past turns)
                 └──> #1 transcript panel (snapshot split)
```
Build the **session reader** + **#5 packaging** early; they unlock the
rest.
