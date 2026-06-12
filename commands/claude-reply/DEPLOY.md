# Deploying `claude-reply`

A Neovim plugin that reformats Claude Code's **Ctrl-G "edit last
response"** buffer (`claude-prompt-*.md`) for email-style quote-reply.
Two steps: **(1)** symlink the lua into your nvim config, **(2)** turn
on Claude Code's `externalEditorContext`. There is **no** Claude
slash-command here, so `deploy.sh command` does **not** apply.

## 1. Symlink the module into nvim

The canonical source lives here; symlink it into your `lua/plugins/`
so lazy.nvim auto-imports it (the `{ import = "plugins" }` glob picks
up every `lua/plugins/*.lua`):

```bash
ln -s /path/to/ai.skillz/commands/claude-reply/claude-reply.lua \
      ~/.config/nvim/lua/plugins/claude-reply.lua
```

For this machine that target resolves through dotrc:

```bash
ln -s ~/repos/ai.skillz/commands/claude-reply/claude-reply.lua \
      ~/repos/dotrc/dotrc/nvim/lua/plugins/claude-reply.lua
```

No edits to `lua/init.lua` or `lua/config/lazy.lua` are needed. The
spec runs `setup_autocmds()` at import and returns `{}` — no remote
plugin to fetch, nothing to `:Lazy install`. Restart nvim (or
`:Lazy reload`) after first install or after editing the file.

> Requires Neovim ≥ 0.9 (`vim.keymap.set`, `nvim_create_autocmd`,
> `vim.opt_local`). Verified on 0.12.

## 2. Enable `externalEditorContext` in Claude Code

This is what makes **Ctrl-G** include your last response in the editor
buffer (it's **off** by default). It's a per-user toggle:

```
/config        → toggle "Show last response in external editor" → on
```

(Stored in your Claude Code config, not a repo `settings.json`, so
it's a one-time per-machine setting — not deployable from this repo.)

Without it, Ctrl-G still opens nvim but with only your raw input and
no markers; the plugin then **no-ops** (your normal nvim behavior is
untouched).

## 3. (Optional) distinct colorscheme

Set a colorscheme to use only while editing a `claude-prompt-*.md`
buffer — handy to signal "you're composing a reply". Add to your nvim
config (anywhere that runs at startup, e.g. a `lua/plugins/*.lua` or
your vimrc-lua):

```lua
vim.g.claude_reply_colorscheme = "habamax"
```

The Ctrl-G editor is a dedicated single-buffer nvim, so this is
self-contained; the plugin also restores your previous scheme on
buffer-leave if you open one of these in your main nvim. Unset → no
change.

## Usage

1. `\e` is `<leader>e` — your leader is `\`.
2. In a Claude session, hit **Ctrl-G**. nvim opens
   `claude-prompt-<uuid>.md`: Claude's last response as `# `-reference
   above the *"Write your reply below this line"* marker; cursor parked
   in the empty reply area below it.
3. `[m` / `]m` to move between response sections (folds are open;
   `<Space>` toggles a section fold, `zM`/`zR` collapse/expand all).
4. Put the cursor on what you want to answer, press **`\e`** — it
   drops below the marker as a `> ` blockquote wrapped to col 69, and
   you land in insert mode underneath. Type your reply. On a
   bullet/numbered **list item** this pulls just that item (+ nested
   children); on a heading/prose line, the whole section.
5. Repeat for each section; visually select reference lines + `\e` to
   pull an arbitrary span.
6. `:wq`. Claude receives only the below-marker text (your quotes +
   replies); everything above the marker is dropped.

## Verify

```bash
# headless smoke test against a fixture (no config side effects):
nvim --headless -u NONE -N \
  -c "lua dofile('/path/to/ai.skillz/commands/claude-reply/claude-reply.lua')" \
  -c "edit /tmp/claude-prompt-TEST.md" \
  -c "lua print(vim.b.claude_reply_ready)" -c "qa!"
```

A real check: with `externalEditorContext` on, Ctrl-G in a live
session, `\e` a section, `:wq`, confirm the sent message is just the
quoted + typed text.

## Binding collision (FYI)

`\q` is your global `ListToggle` quickfix toggle (`nav.lua:116`); `\e`
was chosen to avoid it (only a commented-out ALE line referenced `\e`,
`~/.vimrc:364`). All maps are **buffer-local** to `claude-prompt-*.md`,
so nothing global changes. To rebind, point `<leader>e` at a different
key — every map funnels through `<Plug>(ClaudeReplyPull)`.
