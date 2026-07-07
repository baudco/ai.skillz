# Plan: factor `claude-reply` out into a standalone plugin

User directive (2026-07-06): now that the plugin is cross-harness, it
has outgrown `ai.skillz/commands/claude-reply/` (which frames it as a
Claude-Code slash-command sibling — it isn't one). Factor it out as a
**standalone nvim plugin** first, and design toward the py side
becoming a **standalone py-pkg/lib** (the daemon of
`py-extension-plan.md`) within nvim's packaging constraints.

## Naming — DECIDED 2026-07-06: **`ai.reply`**

User choice: `ai.reply`, pairing with `ai.skillz` (and future `ai.*`
siblings). Location: **local repo only for now** (`~/repos/ai.reply`),
publish to a forge later (post-daemon).

The `.` is fully forge/nvim-compatible — `mini.nvim` and its `mini.*`
family are the established precedent for dotted plugin names:
- repo/dir: `~/repos/ai.reply` (a `.nvim` suffix is purely GitHub
  discoverability convention — optional, add only if/when published;
  dotted GH repo names are fine).
- lua: `require("ai.reply")` ← `lua/ai/reply/init.lua` — the `lua/ai/`
  namespace dir intentionally reserves room for future `ai.*` lua
  modules (mini.nvim does exactly this with `lua/mini/*`).
- py: PEP 420 namespace package — import `ai.reply`, dist name
  normalizes to `ai-reply` if ever on PyPI; future `ai.*` py libs
  share the `ai` namespace.
- compat: keep `claude_reply` as a `package.loaded` alias + read old
  `g:claude_reply_*` vars as fallbacks for one transition release.

## Target layout (standard nvim plugin, per roadmap #5)

```
ai-reply.nvim/                     (own git repo)
  lua/ai_reply/init.lua            (module + setup(opts))
  lua/ai_reply/providers/claude.lua,opencode.lua   (roadmap #3 registry)
  lua/ai_reply/pickers.lua session.lua …           (split the 1.4k-line file)
  plugin/ai-reply.lua              (guarded setup() default wiring)
  python/ai_reply_extract.py       (interim single-file extractor)
  doc/ai-reply.txt                 (:help)
  tests/ (plenary-busted, roadmap #4) + Makefile + CI
  README.md LICENSE
```

- `setup(opts)` replaces the `vim.g.claude_reply_*` knobs (keys,
  highlight, colorscheme, grepper, python, opencode toggle); vim.g
  read as fallback for one release.
- lazy spec for users: `{ "goodboy/ai-reply.nvim", opts = {...} }`
  (load on the compose-file autocmd patterns; costs nothing else).
- ai.skillz keeps a pointer README under `commands/claude-reply/`
  (or vendors the repo as a submodule) — decide with the user; their
  dotrc symlink flips to the new repo path.

## py-pkg constraints + path

- Interim: the extractor script stays a **zero-dep stdlib single
  file** shipped inside the plugin repo (`python/`), resolved relative
  to the lua like today — no venv/pip needed on any host = the only
  truly portable "nvim packaging" for py.
- Endgame (`py-extension-plan.md`): the daemon becomes a real pkg
  (`uv`-managed, py313 venv convention, NixOS-safe) that the plugin
  *talks to* but never imports — nvim plugins can't ship venvs, so
  the decoupled-RPC-daemon design is precisely what sidesteps nvim's
  py packaging constraints. Discovery: socket path convention +
  `g:`/`setup()` override; modden wks spawns the daemon (see
  py-extension-plan remote section).

## Migration steps (when executed)

1. Decide name + repo host (github user repo? local bare?) with user.
2. `git subtree split` the `commands/claude-reply/` history into the
   new repo (preserves the commit trail) OR fresh repo + module split
   refactor as the first commit series.
3. Split the monolith lua into modules; rename module/globals with
   compat shims; port the ad-hoc headless suites to plenary (#4).
4. Flip the dotrc symlink -> lazy spec pointing at the repo; keep the
   ai.skillz copy as pointer/submodule per user choice.
5. Follow-on: provider-profile registry (#3), then the py daemon.

## Ordering vs other work

Do AFTER the current feature wave is committed; it's a pure
restructure (no behavior change) and pairs naturally with roadmap #4
(tests) + #5 (packaging) which it subsumes.
