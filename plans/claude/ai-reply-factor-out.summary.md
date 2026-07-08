Factor out `ai.reply` plugin

- Seed `~/repos/ai.reply` from `commands/claude-reply` with subtree
  history.
- Move the monolith to `lua/ai/reply/init.lua` and the opencode
  extractor to `python/ai_reply_extract.py`.
- Add guarded startup wiring in `plugin/ai-reply.lua`.
- Split plugin logic into `config`, `markers`, `view`, `pull`,
  `pickers`, and provider modules for Claude and opencode.
- Add `setup(opts)` with legacy `g:claude_reply_*` fallbacks, old module
  alias compatibility, old command aliases, old plug mapping, and
  highlight-group links.
- Add plenary-busted coverage for markers, compatibility, pull behavior,
  Claude compact-jsonl parsing, and opencode injection/write stripping.
- Update `README.md` and `DEPLOY.md` for the standalone local lazy.nvim
  plugin layout.
- Flip dotrc to load `~/repos/ai.reply` via `lua/plugins/ai-reply.lua`.
- Replace `ai.skillz/commands/claude-reply` with a pointer README.

Verification:

- `nvim --headless --noplugin -u tests/minimal_init.lua -c
  "PlenaryBustedDirectory tests/ {minimal_init='tests/minimal_init.lua'}"`
  passes 11 specs with 0 failures.
- Headless compose smoke confirms `:AiReplyGrep`, `:ClaudeReplyGrep`,
  quote pull, and `v:lua.require'ai.reply'.foldexpr(v:lnum)`.
- `git diff --check` passes in `~/repos/ai.reply`.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
