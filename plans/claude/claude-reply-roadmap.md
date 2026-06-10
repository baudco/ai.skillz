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

**Approach:** a buffer-local command/keymap (e.g. `:ClaudeReplyPick`
or `\E`) that, from inside the compose buffer:
1. reads the session transcript (shared reader above),
2. lists prior assistant turns via `vim.ui.select` (or telescope/fzf
   if present) — preview first line + timestamp,
3. on pick, runs the chosen turn's text through the **existing**
   de-hash→section→`gq`-wrap→`> `-quote machinery and drops it below
   the marker, exactly like `\e` does for the current reference.

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
