# Plan: `claude-reply` as a python extension (+ modden integration)

Research + design options for porting/hoisting the plugin's data layer
into python with a modern async nvim client. **Status: research done,
design options laid out — BLOCKED on the user's full brain-dump of the
modden integration ideas before committing to a design.**

## Research findings (2026-07-06)

### "Old style" vs "new style" remote plugins (the user's question)

- **Old style** = the legacy embedded `:python`/`:pyfile` interface:
  python runs *inside* nvim's process loop via the `python3` provider,
  synchronous, blocks the editor, no real plugin structure.
- **"New style" (rplugins)** = what
  [pynvim's remote-plugins doc](https://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html)
  describes: you ship `rplugin/python3/<name>.py` containing a class
  decorated with `@pynvim.plugin`, whose methods declare
  `@pynvim.command/@pynvim.function/@pynvim.autocmd` handlers. nvim
  runs a separate **python plugin-host process** and talks msgpack-rpc
  to it. The catch: nvim discovers the handlers via a **manifest**
  that must be (re)generated with `:UpdateRemotePlugins` after every
  spec change — a lifecycle wart core wants gone:
  [neovim/neovim#5532](https://github.com/neovim/neovim/issues/5532)
  (deprecate `:UpdateRemotePlugins`) and especially
  [neovim/neovim#27949](https://github.com/neovim/neovim/issues/27949)
  ("simplify remote plugins, massively") which proposes replacing
  rplugins with plain **"remote modules"**: just a process that
  imports a client lib, connects, and serves RPC requests — no
  manifest, no host, you own the lifecycle.
- Takeaway: building on the rplugin-host machinery today is
  *legacy-leaning*; the forward-compatible pattern is the **standalone
  RPC client process** attached to `nvim --listen` /
  `v:servername` — which is also exactly the shape a modden-managed
  daemon wants.

### Client library options (the async question)

- [pynvim](https://github.com/neovim/pynvim) (v0.6.0, the official
  client) is the ONLY maintained python client; its event loop is
  **asyncio-locked** (the loop abstraction in
  `pynvim/msgpack_rpc/event_loop/{base,asyncio}.py` has a single
  concrete impl — [PR #294](https://github.com/neovim/pynvim/pull/294)
  consolidated on asyncio years ago). No trio/anyio hook point.
- **No trio/anyio nvim client exists**: PyPI probes for
  `nvim-client`/`trio-nvim`/`anyio-nvim`/`aionvim`/`neovim-trio`/etc.
  all 404; web search surfaces only pynvim + dead forks.
- BUT the wire protocol is tiny: msgpack-rpc = 4-element arrays
  (`[type, msgid, method, args]`) over a unix/TCP socket. A minimal
  **anyio-native client** is ~150-250 lines (msgpack + anyio stream +
  request/notify dispatch) covering everything this plugin needs
  (`nvim_buf_get_lines/set_lines`, `nvim_exec_lua`, `nvim_command`,
  event subscription).

## Design options

A. **pynvim rplugin host** (`@pynvim.plugin`): most-documented path;
   asyncio-only, `:UpdateRemotePlugins` wart, host lifecycle owned by
   nvim, core wants to redesign it. NOT recommended.
B. **pynvim as a library** in a standalone process (attach via
   socket): drops the manifest wart, keeps asyncio (bridgeable to
   trio via `trio-asyncio`, meh). Fine fallback.
C. **anyio-native minimal client, standalone daemon** (recommended
   pending brain-dump): small bespoke `nvim_rpc` module (anyio ->
   runs under trio natively — tractor-friendly); the compose-buffer
   nvim exposes its socket (`v:servername` is set automatically, or
   spawn-side `--listen`); the daemon does the data layer the lua
   currently shells out for: session/turn indexing (claude jsonl +
   opencode sqlite), watching (`~/.claude/sessions/<pid>.json`,
   history.jsonl tails), maybe a live transcript panel feed. The lua
   side shrinks toward pure UI (markers/folds/gq/pickers).
   modden/gish angle: the daemon is a natural modden service; `gish`
   as the transport/control plane across harness sessions (see
   project memory) — could serve MULTIPLE nvims + harnesses at once,
   making the cross-harness pickers instant (one warm index instead
   of per-keypress python spawns).

## Open questions for the user's brain-dump (ASK FIRST)

1. What exactly should move to python — just the extractors/indexing
   (fast, warm cache), or interactive features too (live panel,
   session watching, notifications)?
2. Daemon lifecycle: modden-managed service? per-nvim child? on-demand
   socket activation?
3. Where does `gish` sit — transport between daemon<->harnesses,
   daemon<->nvim, or both?
4. tractor in the loop (daemon as a tractor actor tree?) or plain
   trio + anyio?
5. Packaging: `uv`-managed venv under `py313/` (repo convention);
   does the nvim-side stay a lazy.nvim plugin that just *finds* the
   daemon socket?

## Sources

- https://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html
- https://github.com/neovim/pynvim
- https://github.com/neovim/neovim/issues/27949
- https://github.com/neovim/neovim/issues/5532
- https://github.com/neovim/pynvim/pull/294
- https://neovim.io/doc/user/remote_plugin.html
