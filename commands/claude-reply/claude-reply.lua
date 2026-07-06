-- claude-reply.lua
--
-- Augment an AI-CLI's external-editor prompt buffer with an
-- email-style quote-reply workflow. Providers:
--
--   * Claude Code — `claude-prompt-*.md` on Ctrl-G (needs the
--     `externalEditorContext` setting); Claude writes the reference
--     itself and strips it back out on save.
--   * opencode — `<tmpdir>/<epoch-ms>.md` on `editor_open` (ctrl+e);
--     opencode writes only the prompt draft, so THIS plugin injects
--     the last-reply reference (via `oc-last-reply.py`) and strips it
--     on save (`BufWriteCmd`) since opencode reads the whole file
--     back as the prompt.
--
-- The buffer Claude Code hands nvim looks like:
--
--     # ─── Claude's last response (for reference; removed on save) ───
--     # <every response line, '# '-prefixed; bare '#' == original blank>
--     # ─── Write your reply below this line ──────────────────────────
--
--     <empty reply area>
--
-- Claude Code DISCARDS everything at/above the "Write your reply below
-- this line" marker on save and sends only what is below it. So this
-- module DE-HASHES the reference (strips the `# ` prefixes between the
-- markers) into plain markdown — the native md highlighter then lights
-- it up, and since the send is bounded by the marker LINE (not by the
-- `#`), the prefixes need no re-injection. Marker lines are kept
-- verbatim. It then works on the reply area below the marker:
--
--   ]m / [m   jump between Claude's response sections (in the reference)
--   <leader>e pull the section under the cursor down below the marker as
--             a `gq`-wrapped `> ` blockquote, ready for an inline reply
--   <leader>e (visual) pull the selected reference lines
--
-- Self-contained: all logic hangs off the local table `M`, registered as
-- `package.loaded["claude_reply"]` so `foldexpr` / buffer maps can
-- `require` it; the file runs `M.setup_autocmds()` at import time (lazy
-- requires every `lua/plugins/*.lua` at startup) and returns an empty
-- spec — no remote plugin to fetch.

local M = {}

-- U+2500 (─) — the box-drawing rule that prefixes BOTH marker lines.
-- written as raw bytes: LuaJIT (nvim) has no `\u{}` string escape.
local BOX = "\226\148\128"
local REPLY_TXT = "Write your reply below this line"
-- generic phrase: matches Claude Code's own header ("Claude's last
-- response …") AND the one this plugin writes for opencode
-- ("opencode's last response …").
local HEAD_TXT = "last response"

-- ── buffer scan ────────────────────────────────────────────────────

-- A marker line is `# ───… <phrase> …───` — note the U+2500 box rule
-- immediately after "# ". Anchoring on that rule is what stops a
-- response line that merely *mentions* the phrase in prose (these very
-- docs do!) from being mistaken for the real marker — Claude Code
-- prefixes every response line with "# ", so prose never starts "# ─".
local function is_reply_marker(line)
  return line:find("^# " .. BOX) ~= nil and line:find(REPLY_TXT, 1, true) ~= nil
end

local function is_header_marker(line)
  return line:find("^# " .. BOX) ~= nil and line:find(HEAD_TXT, 1, true) ~= nil
end

local function is_marker(line)
  return is_reply_marker(line) or is_header_marker(line)
end

-- returns { header = <1-based|nil>, reply = <1-based|nil> }, lines
function M.find_markers(buf)
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local header, reply
  for i, line in ipairs(lines) do
    if not reply and is_reply_marker(line) then
      reply = i
    elseif not header and is_header_marker(line) then
      header = i
    end
  end
  return { header = header, reply = reply }, lines
end

-- the reference is DE-HASHED on open (see `strip_reference`) so it is
-- plain markdown — these predicates therefore classify raw md lines.
local function ref_is_blank(line)
  return line:match("^%s*$") ~= nil
end

local function ref_is_heading(line)
  return line:match("^#+%s") ~= nil
end

-- recover original response text from a `# `-prefixed reference line:
-- "# foo" -> "foo"   "#" -> ""   "#   " -> ""   "# ## h" -> "## h"
local function dehash(line)
  if line:match("^#%s*$") then
    return ""
  end
  local rest = line:match("^# (.*)$")
  if rest ~= nil then
    return rest
  end
  return (line:gsub("^#", "", 1))
end

-- returns the leading-indent string if `line` begins a markdown list
-- item (bullet `-`/`*`/`+` or numbered `1.`/`1)`), else nil.
local function list_item_indent(line)
  return line:match("^(%s*)[-*+] ") or line:match("^(%s*)%d+[%.%)] ")
end

-- span of the single list item starting at `cur`: the item line plus
-- any following deeper-indented lines (wrapped continuations + nested
-- children), bounded by the section end `e`. 1-based inclusive.
local function item_bounds_at(lines, e, cur)
  local ind = list_item_indent(lines[cur])
  if not ind then
    return nil
  end
  local last = cur
  while last < e do
    local nxt = lines[last + 1]
    local nind = nxt:match("^(%s*)") or ""
    if not ref_is_blank(nxt) and #nind > #ind then
      last = last + 1
    else
      break
    end
  end
  return cur, last
end

-- section == maximal run of non-blank reference lines; a heading line
-- also STARTS a new section. all args/returns 1-based inclusive.
local function section_bounds_at(lines, lo, hi, cur)
  if cur < lo or cur > hi then
    return nil
  end
  local cur_line = lines[cur]
  if ref_is_blank(cur_line) or is_marker(cur_line) then
    return nil
  end
  local s = cur
  while s > lo do
    if ref_is_blank(lines[s - 1]) then
      break
    end
    if ref_is_heading(lines[s]) then
      break
    end
    s = s - 1
  end
  local e = cur
  while e < hi do
    if ref_is_blank(lines[e + 1]) then
      break
    end
    if ref_is_heading(lines[e + 1]) then
      break
    end
    e = e + 1
  end
  return s, e
end

-- ── navigation: ]m / [m ────────────────────────────────────────────

local function warn(msg)
  vim.api.nvim_echo({ { "claude-reply: " .. msg, "WarningMsg" } }, false, {})
end

function M.nav_section(buf, dir)
  buf = buf or vim.api.nvim_get_current_buf()
  local mk, lines = M.find_markers(buf)
  if not mk.reply then
    return
  end
  local lo = (mk.header or 0) + 1
  local hi = mk.reply - 1
  if hi < lo then
    return
  end

  local function is_start(i)
    if i < lo or i > hi then
      return false
    end
    local line = lines[i]
    if ref_is_blank(line) or is_marker(line) then
      return false
    end
    if i == lo or ref_is_heading(line) then
      return true
    end
    return ref_is_blank(lines[i - 1])
  end

  -- anchor just outside the region so a section sitting exactly on the
  -- region edge is still considered when coming from the reply area.
  local cur = vim.fn.line(".")
  local from
  if cur < lo then
    from = lo - 1
  elseif cur > hi then
    from = hi + 1
  else
    from = cur
  end

  local i = from + dir
  while i >= lo and i <= hi do
    if is_start(i) then
      vim.api.nvim_win_set_cursor(0, { i, 0 })
      return
    end
    i = i + dir
  end
  warn("no more sections")
end

-- ── pull a section down as a wrapped blockquote ────────────────────

-- run fn with buffer-local format options forced for a faithful `gq`
-- over `> ` blockquote lines, then restore. every option is
-- buffer-local, so nothing leaks to other buffers.
function M.with_format_opts(buf, fn)
  local bo = vim.bo[buf]
  local save = {
    tw = bo.textwidth,
    fo = bo.formatoptions,
    com = bo.comments,
    fex = bo.formatexpr,
    fp = bo.formatprg,
  }
  bo.textwidth = 69
  local fo = bo.formatoptions
  if not fo:find("q") then
    fo = fo .. "q"
  end
  if not fo:find("n") then
    fo = fo .. "n"
  end
  bo.formatoptions = fo
  if not bo.comments:find("n:>", 1, true) then
    bo.comments = bo.comments .. ",n:>"
  end
  -- force builtin gq (ignore any markdown formatexpr/formatprg)
  bo.formatexpr = ""
  bo.formatprg = ""
  local ok, err = pcall(fn)
  bo.textwidth = save.tw
  bo.formatoptions = save.fo
  bo.comments = save.com
  bo.formatexpr = save.fex
  bo.formatprg = save.fp
  if not ok then
    error(err)
  end
end

-- orig == list of ORIGINAL (prefix-stripped) lines.
function M.pull_section(buf, orig)
  buf = buf or vim.api.nvim_get_current_buf()
  local mk = M.find_markers(buf)
  if not mk.reply then
    return
  end
  -- blank lines become a bare ">" (no trailing space: survives a
  -- trailing-whitespace strip and reflows cleanly under gq).
  local quoted = {}
  for _, t in ipairs(orig) do
    quoted[#quoted + 1] = (t == "") and ">" or ("> " .. t)
  end
  while quoted[1] == ">" do
    table.remove(quoted, 1)
  end
  while #quoted > 0 and quoted[#quoted] == ">" do
    quoted[#quoted] = nil
  end
  if #quoted == 0 then
    warn("nothing to quote here")
    return
  end

  local last = vim.api.nvim_buf_line_count(buf)
  local prev = vim.api.nvim_buf_get_lines(buf, last - 1, last, false)[1] or ""
  local block = {}
  if prev ~= "" then
    block[#block + 1] = ""
  end
  vim.list_extend(block, quoted)
  block[#block + 1] = ""
  vim.api.nvim_buf_set_lines(buf, last, last, false, block)

  local insert_start = last + ((prev ~= "") and 1 or 0) + 1
  local insert_end = insert_start + #quoted - 1

  M.with_format_opts(buf, function()
    vim.api.nvim_win_set_cursor(0, { insert_start, 0 })
    vim.cmd(string.format("normal! %dGV%dGgq", insert_start, insert_end))
  end)

  -- park on the trailing blank (still the last line) and drop into
  -- insert so the reply can be typed immediately.
  local newlast = vim.api.nvim_buf_line_count(buf)
  vim.api.nvim_win_set_cursor(0, { newlast, 0 })
  vim.cmd("startinsert")
end

function M.pull_under_cursor(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local mk, lines = M.find_markers(buf)
  if not mk.reply then
    return
  end
  local lo = (mk.header or 0) + 1
  local hi = mk.reply - 1
  local cur = vim.fn.line(".")
  if cur >= mk.reply then
    warn("cursor is not in the reference (move up, or use ]m / [m)")
    return
  end
  local s, e = section_bounds_at(lines, lo, hi, cur)
  if not s then
    warn("no section here (try ]m / [m)")
    return
  end
  -- DWIM granularity: on a list item, pull just that item (+ its
  -- indented children); on a heading/prose line, the whole section.
  -- whole-section from an item == put the cursor on the heading, or
  -- V-select the span.
  local is, ie = item_bounds_at(lines, e, cur)
  if is then
    s, e = is, ie
  end
  local orig = {}
  for i = s, e do
    orig[#orig + 1] = lines[i] -- reference is already de-hashed markdown
  end
  M.pull_section(buf, orig)
end

function M.pull_visual(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local mk, lines = M.find_markers(buf)
  if not mk.reply then
    return
  end
  local lo = (mk.header or 0) + 1
  local hi = mk.reply - 1
  local vs = math.max(vim.fn.line("'<"), lo)
  local ve = math.min(vim.fn.line("'>"), hi)
  if ve < vs then
    warn("selection has no reference lines")
    return
  end
  local orig = {}
  for i = vs, ve do
    if not is_marker(lines[i]) then
      orig[#orig + 1] = lines[i] -- reference is already de-hashed markdown
    end
  end
  M.pull_section(buf, orig)
end

-- ── folds: reference region, by section, open by default ───────────

function M.foldexpr(lnum)
  local buf = vim.api.nvim_get_current_buf()
  local lo = vim.b[buf].claude_reply_lo
  local hi = vim.b[buf].claude_reply_hi
  if not lo or lnum < lo or lnum > hi then
    return "0"
  end
  local line = vim.fn.getline(lnum)
  if line:match("^%s*$") then
    return "0"
  end
  if line:match("^#+%s") or lnum == lo then
    return ">1"
  end
  if vim.fn.getline(lnum - 1):match("^%s*$") then
    return ">1"
  end
  return "1"
end

-- ── re-inflate a truncated reference from the session transcript ───
--
-- Claude Code hard-caps the Ctrl-G reference at the last 50 lines
-- (`rh4=50` in the binary, no setting), prepending a sentinel line
-- `… (earlier output truncated)`. The FULL reply is on disk though, in
-- the session transcript (`<config>/projects/<cwd-slug>/<uuid>.jsonl`),
-- so when the sentinel is present we reconstruct the last reply from
-- the transcript and swap it into the reference region. A candidate
-- transcript is only accepted if the visible truncated lines match the
-- TAIL of its reconstructed reply — so a concurrent session in the
-- same cwd can never inflate the wrong conversation.

local SENTINEL = "\226\128\166 (earlier output truncated)" -- "… (…)"

local function transcript_dir()
  local override = vim.g.claude_reply_transcript_dir
  if override and override ~= "" then
    return override
  end
  local cfg = vim.env.CLAUDE_CONFIG_DIR or (vim.env.HOME .. "/.claude")
  -- slug == cwd with every non-alphanumeric char (incl. '.') -> '-'
  local slug = vim.fn.getcwd():gsub("[^%w]", "-")
  return cfg .. "/projects/" .. slug
end

-- *.jsonl in dir, most-recently-modified first
local function list_transcripts(dir)
  local fs = vim.uv or vim.loop
  local out = {}
  local h = fs.fs_scandir(dir)
  if not h then
    return out
  end
  while true do
    local name, t = fs.fs_scandir_next(h)
    if not name then
      break
    end
    if name:match("%.jsonl$") and t ~= "directory" then
      local st = fs.fs_stat(dir .. "/" .. name)
      if st then
        out[#out + 1] = { path = dir .. "/" .. name, mtime = st.mtime.sec }
      end
    end
  end
  table.sort(out, function(a, b)
    return a.mtime > b.mtime
  end)
  return out
end

-- reconstruct the "last reply" exactly as Claude's context builder
-- (`WG4`) does, but without the 50-line display cut: forward-scan the
-- jsonl, RESET the accumulator on every real user prompt (not isMeta,
-- not a tool_result carrier, not a sidechain), collect assistant text
-- blocks (skip thinking/tool_use and sidechain agents), join messages
-- with blank lines, mirror WG4's 8-message/64KB caps.
function M.last_reply_text(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local msgs = {}
  for line in f:lines() do
    -- cheap prefilter; full classification happens post-decode
    if line:find('"type":"assistant"', 1, true) or line:find('"type":"user"', 1, true) then
      local ok, obj = pcall(vim.json.decode, line)
      if ok and type(obj) == "table" and not obj.isSidechain then
        if obj.type == "assistant" and obj.message and type(obj.message.content) == "table" then
          local parts = {}
          for _, blk in ipairs(obj.message.content) do
            if type(blk) == "table" and blk.type == "text" and type(blk.text) == "string" then
              parts[#parts + 1] = blk.text
            end
          end
          local txt = vim.trim(table.concat(parts, "\n\n"))
          if txt ~= "" then
            msgs[#msgs + 1] = txt
          end
        elseif obj.type == "user" and not obj.isMeta then
          local c = obj.message and obj.message.content
          local is_tool_result = false
          if type(c) == "table" then
            for _, blk in ipairs(c) do
              if type(blk) == "table" and blk.type == "tool_result" then
                is_tool_result = true
                break
              end
            end
          end
          if not is_tool_result then
            msgs = {} -- real user prompt: reply restarts after this
          end
        end
      end
    end
  end
  f:close()
  if #msgs == 0 then
    return nil
  end
  local keep, bytes = {}, 0
  for i = #msgs, 1, -1 do
    local b = #msgs[i]
    if #keep >= 8 or (#keep > 0 and bytes + b > 65536) then
      break
    end
    table.insert(keep, 1, msgs[i])
    bytes = bytes + b
  end
  return table.concat(keep, "\n\n")
end

-- like `last_reply_text` but keeps EVERY turn: a real user prompt
-- CLOSES the accumulated turn instead of discarding it. returns an
-- ordered (oldest-first) list of { text, ts } or nil.
function M.all_replies(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local turns, msgs, ts = {}, {}, nil
  local function close_turn()
    if #msgs > 0 then
      turns[#turns + 1] = { text = table.concat(msgs, "\n\n"), ts = ts }
      msgs, ts = {}, nil
    end
  end
  for line in f:lines() do
    if line:find('"type":"assistant"', 1, true) or line:find('"type":"user"', 1, true) then
      local ok, obj = pcall(vim.json.decode, line)
      if ok and type(obj) == "table" and not obj.isSidechain then
        if obj.type == "assistant" and obj.message and type(obj.message.content) == "table" then
          local parts = {}
          for _, blk in ipairs(obj.message.content) do
            if type(blk) == "table" and blk.type == "text" and type(blk.text) == "string" then
              parts[#parts + 1] = blk.text
            end
          end
          local txt = vim.trim(table.concat(parts, "\n\n"))
          if txt ~= "" then
            msgs[#msgs + 1] = txt
            ts = ts or obj.timestamp
          end
        elseif obj.type == "user" and not obj.isMeta then
          local c = obj.message and obj.message.content
          local is_tool_result = false
          if type(c) == "table" then
            for _, blk in ipairs(c) do
              if type(blk) == "table" and blk.type == "tool_result" then
                is_tool_result = true
                break
              end
            end
          end
          if not is_tool_result then
            close_turn()
          end
        end
      end
    end
  end
  f:close()
  close_turn()
  return #turns > 0 and turns or nil
end

local function rstrip(s)
  return (s:gsub("%s+$", ""))
end

-- visible truncated lines must equal the tail of the full reply
local function tail_matches(full, visible)
  if #visible == 0 or #full < #visible then
    return false
  end
  local off = #full - #visible
  for i = 1, #visible do
    if rstrip(full[off + i]) ~= rstrip(visible[i]) then
      return false
    end
  end
  return true
end

-- returns true if the reference region was replaced (markers moved!)
local function reinflate(buf, mk)
  if vim.g.claude_reply_reinflate == false then
    return false
  end
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local lo = (mk.header or 0) + 1
  if lo > mk.reply - 1 then
    return false
  end
  if not lines[lo]:find(SENTINEL, 1, true) then
    return false -- not truncated: nothing to do
  end
  local visible = {}
  for i = lo + 1, mk.reply - 1 do
    visible[#visible + 1] = dehash(lines[i])
  end
  for _, ent in ipairs(list_transcripts(transcript_dir())) do
    local txt = M.last_reply_text(ent.path)
    if txt then
      local full = vim.split(txt, "\n", { plain = true })
      if tail_matches(full, visible) then
        -- swap in the full reply, re-hashed to mirror claude's own
        -- format; the normal de-hash pass below then applies uniformly
        local hashed = {}
        for _, l in ipairs(full) do
          hashed[#hashed + 1] = (l == "") and "#" or ("# " .. l)
        end
        vim.api.nvim_buf_set_lines(buf, lo - 1, mk.reply - 1, false, hashed)
        return true
      end
    end
  end
  warn("could not re-inflate truncated reference (no matching transcript)")
  return false
end

-- de-hash the reference (lines between the markers) into plain markdown
-- so the native md highlighter renders it. SAFE: Claude Code bounds the
-- send by the marker LINE, discarding everything above it regardless of
-- `#`, so no re-injection is needed. Marker lines are left untouched
-- (the reply marker must survive verbatim). Runs once per buffer; the
-- edit is marked un-modified so a bare `:q` still aborts cleanly.
local function strip_reference(buf, mk)
  local lo = (mk.header or 0) + 1
  local hi = mk.reply - 1
  if hi < lo then
    return
  end
  local cur = vim.api.nvim_buf_get_lines(buf, lo - 1, hi, false)
  for i, line in ipairs(cur) do
    cur[i] = dehash(line)
  end
  vim.api.nvim_buf_set_lines(buf, lo - 1, hi, false, cur)
  vim.bo[buf].modified = false
end

local function apply_view_opts()
  vim.opt_local.wrap = true
  vim.opt_local.linebreak = true
  vim.opt_local.breakindent = true
  vim.opt_local.showbreak = "↪ "
end

-- highlighting for the de-hashed markdown reference. default "syntax"
-- uses nvim's robust builtin markdown syntax AND detaches treesitter
-- for THIS buffer — a broken or absent markdown TS parser (an easy
-- state to be in) otherwise crashes the highlighter on every redraw of
-- the ephemeral compose buffer. set `vim.g.claude_reply_highlight`:
--   "syntax"      (default) legacy md syntax, treesitter off here
--   "treesitter"  leave whatever your config attached (only if it works)
--   "off"         no highlighting
local function apply_highlight(buf)
  local mode = vim.g.claude_reply_highlight or "syntax"
  if mode == "treesitter" then
    return
  end
  pcall(vim.treesitter.stop, buf)
  pcall(function()
    vim.bo[buf].syntax = (mode == "off") and "" or "markdown"
  end)
end

-- apply now, then again on the next tick: filetype detection (which
-- attaches treesitter via FileType) may run after our BufReadPost, so
-- the deferred pass guarantees we detach TS last.
local function ensure_highlight(buf)
  apply_highlight(buf)
  vim.schedule(function()
    if vim.api.nvim_buf_is_valid(buf) then
      apply_highlight(buf)
    end
  end)
end

-- optional: a distinct colorscheme while editing a claude-prompt
-- buffer. set `vim.g.claude_reply_colorscheme = "<name>"` to enable.
-- because Ctrl-G spawns a dedicated single-buffer nvim, applying it
-- globally there is self-contained; the BufEnter/BufLeave pair below
-- also keeps it tidy if one is ever opened inside your main nvim.
local function setup_colorscheme(buf)
  local cs = vim.g.claude_reply_colorscheme
  if not cs or cs == "" then
    return
  end
  local prev = vim.g.colors_name
  local function apply()
    pcall(vim.cmd.colorscheme, cs)
  end
  local function restore()
    if prev and prev ~= "" then
      pcall(vim.cmd.colorscheme, prev)
    end
  end
  apply()
  local grp = vim.api.nvim_create_augroup("ClaudeReplyColors_" .. buf, { clear = true })
  vim.api.nvim_create_autocmd("BufEnter", { group = grp, buffer = buf, callback = apply })
  vim.api.nvim_create_autocmd({ "BufLeave", "BufWinLeave" }, { group = grp, buffer = buf, callback = restore })
end

local function apply_folds(buf, mk)
  vim.b[buf].claude_reply_lo = (mk.header or 0) + 1
  vim.b[buf].claude_reply_hi = mk.reply - 1
  vim.opt_local.foldmethod = "expr"
  vim.opt_local.foldexpr = "v:lua.require'claude_reply'.foldexpr(v:lnum)"
  vim.opt_local.foldenable = true
  vim.opt_local.foldlevel = 99
end

-- ── maps ───────────────────────────────────────────────────────────

local function setup_maps(buf)
  local function opts(desc)
    return { buffer = buf, silent = true, desc = "claude-reply: " .. desc }
  end
  vim.keymap.set("n", "]m", function()
    M.nav_section(buf, 1)
  end, opts("next response section"))
  vim.keymap.set("n", "[m", function()
    M.nav_section(buf, -1)
  end, opts("prev response section"))

  vim.keymap.set("n", "<Plug>(ClaudeReplyPull)", function()
    M.pull_under_cursor(buf)
  end, { buffer = buf, silent = true })
  vim.keymap.set(
    "x",
    "<Plug>(ClaudeReplyPull)",
    ":<C-u>lua require'claude_reply'.pull_visual()<CR>",
    { buffer = buf, silent = true }
  )

  vim.keymap.set("n", "<leader>e", "<Plug>(ClaudeReplyPull)", {
    buffer = buf,
    remap = true,
    silent = true,
    desc = "claude-reply: pull section as quote",
  })
  vim.keymap.set("x", "<leader>e", "<Plug>(ClaudeReplyPull)", {
    buffer = buf,
    remap = true,
    silent = true,
    desc = "claude-reply: pull selection as quote",
  })

  -- prior-reply picker (shadows the global vimrc-source \r map ONLY
  -- inside compose buffers)
  vim.keymap.set("n", "<leader>r", function()
    M.pick_reply(buf)
  end, opts("pick a prior reply (page/quote)"))
  vim.api.nvim_buf_create_user_command(buf, "ClaudeReplyPick", function()
    M.pick_reply(buf)
  end, { desc = "claude-reply: pick a prior reply" })
end

-- provider-shared UI wiring: view opts, folds, highlight, colors,
-- maps, cursor park (at `park`, clamped to the buffer). must precede
-- every provider's setup fn (plain local, no forward declaration).
local function setup_ui(buf, mk, park)
  apply_view_opts()
  apply_folds(buf, mk)
  ensure_highlight(buf)
  setup_colorscheme(buf)
  park = math.min(park, vim.api.nvim_buf_line_count(buf))
  vim.api.nvim_win_set_cursor(0, { park, 0 })
  setup_maps(buf)
end

-- ── opencode provider ──────────────────────────────────────────────
--
-- opencode's `editor_open` (ctrl+e) writes the CURRENT PROMPT DRAFT to
-- `<os.tmpdir()>/<Date.now()>.md`, spawns $VISUAL||$EDITOR on it
-- (blocking, TUI suspended), then reads the WHOLE file back into the
-- prompt box (verified in the 1.17.9 bundle, fn `ue`). Unlike Claude
-- Code it neither includes the last reply nor strips anything on save,
-- so this provider does both: inject the reference (fetched from
-- opencode's session store by `oc-last-reply.py`) above a reply
-- marker, and strip at/above the marker on write via `BufWriteCmd`.
-- The reference is injected as PLAIN markdown (no `# `-hash dance —
-- that exists only to mirror what Claude Code writes).

-- markers mirror Claude's shape (`# ───… <phrase> …───`) so ALL the
-- shared machinery (find_markers/nav/pull/folds) applies unchanged.
local OC_HEADER = "# " .. BOX:rep(3) .. " opencode's last response (for reference; removed on save) " .. BOX:rep(3)
local OC_REPLY = "# " .. BOX:rep(3) .. " Write your reply below this line " .. BOX:rep(26)

-- this file's real dir (through the deploy symlink) — the extractor
-- script lives beside it.
local function plugin_dir()
  local src = debug.getinfo(1, "S").source:sub(2)
  local real = (vim.uv or vim.loop).fs_realpath(src) or src
  return vim.fn.fnamemodify(real, ":h")
end

-- fetch the last assistant reply for cwd's opencode session, or nil.
-- override the whole command with `vim.g.claude_reply_oc_fetch_cmd`
-- (list, e.g. from tests); pick the interpreter with
-- `vim.g.claude_reply_python`; force the CLI route with
-- `vim.g.claude_reply_oc_via_export = true`.
function M.opencode_last_reply()
  local cmd = vim.g.claude_reply_oc_fetch_cmd
  if not cmd then
    local py = vim.g.claude_reply_python or vim.fn.exepath("python3")
    if py == nil or py == "" then
      warn("opencode: no python3 on PATH (set g:claude_reply_python)")
      return nil
    end
    local script = vim.g.claude_reply_oc_script or (plugin_dir() .. "/oc-last-reply.py")
    cmd = { py, script, "--cwd", vim.fn.getcwd() }
    if vim.g.claude_reply_oc_via_export then
      table.insert(cmd, "--via-export")
    end
  end
  local out = vim.fn.system(cmd)
  if vim.v.shell_error ~= 0 or out == nil or vim.trim(out) == "" then
    return nil
  end
  return out
end

-- the Vt_-equivalent opencode lacks: on write, put ONLY the
-- below-marker content in the file (opencode reads the whole file back
-- as the prompt). if the user deleted the marker, send everything.
local function oc_write(buf)
  local mk, lines = M.find_markers(buf)
  local out
  if mk.reply then
    out = {}
    for i = mk.reply + 1, #lines do
      out[#out + 1] = lines[i]
    end
    if out[1] == "" then
      table.remove(out, 1) -- the separator blank we inserted
    end
  else
    out = lines
  end
  -- drop trailing blank padding (meaningless in a chat prompt)
  while #out > 0 and out[#out]:match("^%s*$") do
    out[#out] = nil
  end
  -- NEVER write a 0-byte file: opencode's read-back treats empty as
  -- "abort" (`content || undefined` in fn `ue`) and would LEAVE THE
  -- OLD PROMPT in place. a lone newline reads back truthy ("\n") and
  -- opencode's own single-trailing-newline strip (`le`) turns it into
  -- "" — so clearing the reply area genuinely CLEARS the prompt box.
  if #out == 0 then
    out = { "" }
  end
  vim.fn.writefile(out, vim.api.nvim_buf_get_name(buf))
  vim.bo[buf].modified = false
end

function M.setup_opencode_buffer(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  if vim.b[buf].claude_reply_ready then
    return
  end
  local mk = M.find_markers(buf)
  if not mk.reply then
    local reply = M.opencode_last_reply()
    if not reply then
      return -- no session/reply for cwd: stay out of the way entirely
    end
    local draft = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
    local block = { OC_HEADER }
    for _, l in ipairs(vim.split(reply, "\n", { plain = true })) do
      -- a reply that itself contains a marker-shaped line (say, a
      -- session about THIS plugin) would hijack find_markers / the
      -- on-write strip — break the `^# ─` anchor with a middot.
      if is_marker(l) then
        l = "·" .. l
      end
      block[#block + 1] = l
    end
    block[#block + 1] = OC_REPLY
    block[#block + 1] = ""
    vim.list_extend(block, draft)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, block)
    vim.bo[buf].modified = false -- bare :q still aborts (draft kept)
    mk = M.find_markers(buf)
  end
  vim.b[buf].claude_reply_ready = true
  vim.b[buf].claude_reply_provider = "opencode"

  vim.api.nvim_create_autocmd("BufWriteCmd", {
    group = vim.api.nvim_create_augroup("ClaudeReplyOcWrite_" .. buf, { clear = true }),
    buffer = buf,
    callback = function()
      oc_write(buf)
    end,
  })

  -- park at buffer end: the user's in-progress draft (if any) sits
  -- below the marker and the reply continues after it.
  setup_ui(buf, mk, vim.api.nvim_buf_line_count(buf))
end

-- ── prior-reply picker: page/quote any earlier turn ────────────────
--
-- `\r` (or :ClaudeReplyPick) opens a fuzzy picker over EVERY prior
-- reply of the session — telescope when available (custom picker:
-- fuzzy matches the full reply text via `ordinal`, live markdown
-- preview, user's own sorter/theme), else `vim.ui.select`.
--   <CR>  "reference paging": swap the chosen turn INTO the reference
--         region so the whole ]m/[m + granular \e workflow applies to
--         it; re-pick to page elsewhere (the newest turn == "live").
--   <C-q> quote the whole turn below the marker directly.

-- replace the reference region with `text`; tag the header line with
-- a ⟨#idx/total⟩ paging suffix (the "last response" phrase the marker
-- matcher anchors on is preserved).
function M.set_reference(buf, text, idx, total)
  buf = buf or vim.api.nvim_get_current_buf()
  local mk = M.find_markers(buf)
  if not mk.reply then
    return
  end
  local lo = (mk.header or 0) + 1
  local new = {}
  for _, l in ipairs(vim.split(text, "\n", { plain = true })) do
    if is_marker(l) then
      l = "\194\183" .. l -- '·' defuse, same guard as injection
    end
    new[#new + 1] = l
  end
  vim.api.nvim_buf_set_lines(buf, lo - 1, mk.reply - 1, false, new)
  if mk.header and idx and total then
    local h = vim.api.nvim_buf_get_lines(buf, mk.header - 1, mk.header, false)[1]
    h = h:gsub("%s*⟨#%d+/%d+[^⟩]*⟩%s*$", "")
    local tag = (idx == total) and (" ⟨#%d/%d live⟩"):format(idx, total)
      or (" ⟨#%d/%d⟩"):format(idx, total)
    vim.api.nvim_buf_set_lines(buf, mk.header - 1, mk.header, false, { h .. tag })
  end
  local nmk = M.find_markers(buf)
  apply_folds(buf, nmk) -- region length changed: refresh fold bounds
  vim.bo[buf].modified = false
  vim.api.nvim_win_set_cursor(0, { (nmk.header or 0) + 1, 0 })
end

-- claude: resolve (once, cached) WHICH transcript is this session's by
-- tail-matching the reference visible at first pick — before any
-- paging has replaced it — against each candidate's reconstructed
-- last reply; falls back to the most-recently-modified transcript.
local function resolve_transcript(buf)
  local path = vim.b[buf].claude_reply_transcript
  if path then
    return path
  end
  local mk, lines = M.find_markers(buf)
  local visible = {}
  if mk.reply then
    for i = (mk.header or 0) + 1, mk.reply - 1 do
      visible[#visible + 1] = lines[i]
    end
  end
  local entries = list_transcripts(transcript_dir())
  for _, ent in ipairs(entries) do
    local txt = M.last_reply_text(ent.path)
    if txt and #visible > 0 and tail_matches(vim.split(txt, "\n", { plain = true }), visible) then
      path = ent.path
      break
    end
  end
  path = path or (entries[1] and entries[1].path)
  vim.b[buf].claude_reply_transcript = path
  return path
end

-- ordered (oldest-first) turn list for the buffer's provider
local function fetch_turns(buf)
  if vim.b[buf].claude_reply_provider == "opencode" then
    local cmd = vim.g.claude_reply_oc_list_cmd
    if not cmd then
      local py = vim.g.claude_reply_python or vim.fn.exepath("python3")
      if py == nil or py == "" then
        return nil
      end
      local script = vim.g.claude_reply_oc_script or (plugin_dir() .. "/oc-last-reply.py")
      cmd = { py, script, "--cwd", vim.fn.getcwd(), "--list" }
    end
    local out = vim.fn.system(cmd)
    if vim.v.shell_error ~= 0 then
      return nil
    end
    local ok, turns = pcall(vim.json.decode, out)
    return (ok and type(turns) == "table") and turns or nil
  end
  local path = resolve_transcript(buf)
  return path and M.all_replies(path) or nil
end

-- ts is an ISO string (claude jsonl) or epoch-ms number (opencode db)
local function fmt_ts(ts)
  if type(ts) == "number" then
    return os.date("%H:%M", math.floor(ts / 1000))
  end
  if type(ts) == "string" then
    return ts:match("T(%d%d:%d%d)") or "??:??"
  end
  return "??:??"
end

local function first_line(text)
  for _, l in ipairs(vim.split(text, "\n", { plain = true })) do
    if not l:match("^%s*$") then
      return vim.fn.strcharpart(l, 0, 56)
    end
  end
  return ""
end

function M.pick_reply(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local turns = fetch_turns(buf)
  if not turns or #turns == 0 then
    warn("no prior replies found for this session")
    return
  end
  local total = #turns
  local items = {}
  for i = total, 1, -1 do -- newest first in the list
    local t = turns[i]
    items[#items + 1] = {
      idx = i,
      total = total,
      text = t.text,
      label = ("#%d %s  %s"):format(i, fmt_ts(t.ts), first_line(t.text)),
    }
  end

  local has_telescope, pickers = pcall(require, "telescope.pickers")
  if not has_telescope then
    vim.ui.select(items, {
      prompt = "prior AI replies",
      format_item = function(it)
        return it.label
      end,
    }, function(choice)
      if choice then
        M.set_reference(buf, choice.text, choice.idx, choice.total)
      end
    end)
    return
  end

  local finders = require("telescope.finders")
  local tconf = require("telescope.config").values
  local actions = require("telescope.actions")
  local action_state = require("telescope.actions.state")
  local previewers = require("telescope.previewers")

  pickers
    .new({}, {
      prompt_title = "prior AI replies · <CR> page reference · <C-q> quote turn",
      finder = finders.new_table({
        results = items,
        entry_maker = function(it)
          return {
            value = it,
            display = it.label,
            -- ordinal carries the FULL reply text: fuzzy back-search
            -- matches reply content, not just the label
            ordinal = it.label .. " " .. it.text,
          }
        end,
      }),
      sorter = tconf.generic_sorter({}),
      previewer = previewers.new_buffer_previewer({
        title = "reply",
        define_preview = function(self, entry)
          vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, vim.split(entry.value.text, "\n", { plain = true }))
          pcall(function()
            vim.bo[self.state.bufnr].syntax = "markdown"
          end)
        end,
      }),
      attach_mappings = function(prompt_bufnr, map)
        actions.select_default:replace(function()
          local e = action_state.get_selected_entry()
          actions.close(prompt_bufnr)
          if e then
            M.set_reference(buf, e.value.text, e.value.idx, e.value.total)
          end
        end)
        local quote = function()
          local e = action_state.get_selected_entry()
          actions.close(prompt_bufnr)
          if e then
            M.pull_section(buf, vim.split(e.value.text, "\n", { plain = true }))
          end
        end
        map("i", "<C-q>", quote)
        map("n", "<C-q>", quote)
        return true
      end,
    })
    :find()
end

-- ── per-buffer setup + autocmd ─────────────────────────────────────

function M.setup_buffer(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  if vim.b[buf].claude_reply_ready then
    return
  end
  local mk = M.find_markers(buf)
  if not mk.reply then
    return -- externalEditorContext off / raw input: no-op
  end
  vim.b[buf].claude_reply_ready = true

  if reinflate(buf, mk) then
    mk = M.find_markers(buf) -- region grew: marker line numbers moved
  end
  strip_reference(buf, mk)
  setup_ui(buf, mk, mk.reply + 1)
end

-- re-shown in a new window (split): re-assert window-local view.
-- returns true if the buffer was already initialised.
local function reassert_view(buf)
  if not vim.b[buf].claude_reply_ready then
    return false
  end
  local mk = M.find_markers(buf)
  if mk.reply then
    apply_view_opts()
    apply_folds(buf, mk)
    ensure_highlight(buf)
  end
  return true
end

function M.setup_autocmds()
  local grp = vim.api.nvim_create_augroup("ClaudeReply", { clear = true })
  vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter" }, {
    group = grp,
    pattern = "claude-prompt-*.md",
    callback = function(ev)
      if not reassert_view(ev.buf) then
        M.setup_buffer(ev.buf)
      end
    end,
  })

  -- opencode's prompt temp file: `<os.tmpdir()>/<Date.now()>.md`, i.e.
  -- a 13-digit epoch-ms basename (constant until year 2286). nvim is
  -- spawned BY opencode, so it inherits the same $TMPDIR and
  -- os_tmpdir() here resolves to the very dir opencode used. NB: in
  -- autocmd patterns `*` crosses `/`, hence the strict basename guard
  -- in the callback. kill-switch: `vim.g.claude_reply_opencode = false`.
  local tmp = ((vim.uv or vim.loop).os_tmpdir() or "/tmp"):gsub("/+$", "")
  vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter" }, {
    group = grp,
    pattern = tmp .. "/*.md",
    callback = function(ev)
      if vim.g.claude_reply_opencode == false then
        return
      end
      local name = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(ev.buf), ":t")
      if not name:match("^%d%d%d%d%d%d%d%d%d%d%d%d%d%.md$") then
        return
      end
      if not reassert_view(ev.buf) then
        M.setup_opencode_buffer(ev.buf)
      end
    end,
  })
end

package.loaded["claude_reply"] = M
M.setup_autocmds()

return {}
