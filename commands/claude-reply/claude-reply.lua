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
  -- every user-facing key is configurable; all maps are BUFFER-LOCAL
  -- (they shadow any global binding only inside compose buffers).
  local keys = {
    pull = vim.g.claude_reply_key_pull or "<leader>e",
    replies = vim.g.claude_reply_key_replies or "<leader>r",
    dialogs = vim.g.claude_reply_key_dialogs or "<leader>d",
  }
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

  vim.keymap.set("n", keys.pull, "<Plug>(ClaudeReplyPull)", {
    buffer = buf,
    remap = true,
    silent = true,
    desc = "claude-reply: pull section as quote",
  })
  vim.keymap.set("x", keys.pull, "<Plug>(ClaudeReplyPull)", {
    buffer = buf,
    remap = true,
    silent = true,
    desc = "claude-reply: pull selection as quote",
  })

  -- prior-reply picker (shadows the global vimrc-source \r map ONLY
  -- inside compose buffers)
  vim.keymap.set("n", keys.replies, function()
    M.pick_reply(buf)
  end, opts("pick a prior reply (page/quote)"))
  vim.api.nvim_buf_create_user_command(buf, "ClaudeReplyPick", function()
    M.pick_reply(buf)
  end, { desc = "claude-reply: pick a prior reply" })

  -- cross-harness dialog/session picker (stage 1 of dialog -> turn).
  -- default \d shadows the global :diffupdate map in compose bufs only.
  vim.keymap.set("n", keys.dialogs, function()
    M.pick_session(buf)
  end, opts("pick a dialog (cross-harness), then a reply"))
  for _, cname in ipairs({ "ClaudeReplyDialogs", "ClaudeReplySessions" }) do
    vim.api.nvim_buf_create_user_command(buf, cname, function()
      M.pick_session(buf)
    end, { desc = "claude-reply: pick a dialog, then a reply" })
  end

  -- deep content search over every reply (bang == all projects)
  vim.api.nvim_buf_create_user_command(buf, "ClaudeReplyGrep", function(o)
    M.grep_replies(buf, o.args, o.bang)
  end, { nargs = 1, bang = true, desc = "claude-reply: grep all replies (:! for all projects)" })
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
    -- drop ALL leading blanks (the separator we inserted + any
    -- stragglers) — a leading newline in a chat prompt is noise and
    -- compounds across editor round-trips
    while out[1] and out[1]:match("^%s*$") do
      table.remove(out, 1)
    end
  else
    out = lines
  end
  -- drop trailing blank padding (meaningless in a chat prompt)
  while #out > 0 and out[#out]:match("^%s*$") do
    out[#out] = nil
  end
  local name = vim.api.nvim_buf_get_name(buf)
  if #out == 0 then
    -- NEVER write a 0-byte file: opencode's read-back treats empty as
    -- "abort" (`content || undefined` in fn `ue`) and would LEAVE THE
    -- OLD PROMPT in place. a lone newline reads back truthy ("\n")
    -- and opencode's `le` strips it (single-line case) — the prompt
    -- box genuinely CLEARS.
    vim.fn.writefile({ "" }, name)
  else
    -- binary mode ('b'): NO trailing newline. opencode's `le` only
    -- strips a trailing "\n" from SINGLE-line content — multi-line
    -- content keeps it and renders an extra blank line at the end of
    -- the prompt box (claude strips it itself in `Vt_`, hence
    -- "opencode-only extra line").
    vim.fn.writefile(out, name, "b")
  end
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
    -- strip the draft's LEADING blanks (an empty prompt box arrives
    -- as one empty line): exactly ONE blank sits below the marker,
    -- never two.
    while draft[1] and draft[1]:match("^%s*$") do
      table.remove(draft, 1)
    end
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
-- a ⟨#idx/total⟩ paging suffix — or ⟨<label> #idx/total⟩ when paging a
-- FOREIGN session's turn (the "last response" phrase the marker
-- matcher anchors on is preserved either way).
function M.set_reference(buf, text, idx, total, label)
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
    h = h:gsub("%s*⟨[^⟩]*⟩%s*$", "")
    local tag
    if label and label ~= "" then
      local short = vim.fn.strcharpart(label:gsub("[⟨⟩]", ""), 0, 24)
      tag = (" ⟨%s #%d/%d⟩"):format(short, idx, total)
    else
      tag = (idx == total) and (" ⟨#%d/%d live⟩"):format(idx, total)
        or (" ⟨#%d/%d⟩"):format(idx, total)
    end
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

-- short-TTL caches: session lists + foreign-session turn fetches.
-- kills the <C-o> back-out lag (each stage-1 rebuild was 2 batched
-- greps + a python spawn). the py-daemon plan is the real fix; this
-- is the interim one.
local CACHE_TTL_MS = 45000
local session_cache = {}
local turns_cache = {}

local function cache_get(tbl, key)
  local hit = tbl[key]
  if hit and ((vim.uv or vim.loop).now() - hit.at) < CACHE_TTL_MS then
    return hit.val
  end
  return nil
end

local function cache_put(tbl, key, val)
  tbl[key] = { at = (vim.uv or vim.loop).now(), val = val }
  return val
end

-- run the extractor with `extra` args and decode its JSON stdout.
-- `override` (a vim.g test hook) replaces the whole command when set.
local function oc_json(extra, override)
  local cmd = override
  if not cmd then
    local py = vim.g.claude_reply_python or vim.fn.exepath("python3")
    if py == nil or py == "" then
      return nil
    end
    local script = vim.g.claude_reply_oc_script or (plugin_dir() .. "/oc-last-reply.py")
    cmd = { py, script, "--cwd", vim.fn.getcwd() }
    vim.list_extend(cmd, extra)
  end
  local out = vim.fn.system(cmd)
  if vim.v.shell_error ~= 0 then
    return nil
  end
  local ok, val = pcall(vim.json.decode, out)
  return (ok and type(val) == "table") and val or nil
end

-- ordered (oldest-first) turn list. `src` targets an explicit session
-- ({provider="claude", path=…} | {provider="opencode", session=…});
-- nil == the buffer's own current session.
local function fetch_turns(buf, src)
  if src then
    -- foreign-session fetches are TTL-cached (preview hovers + <C-o>
    -- round-trips re-request the same turns constantly); the CURRENT
    -- session is never cached — it can grow under us.
    local key = src.provider .. ":" .. (src.path or src.session or "?")
    local hit = cache_get(turns_cache, key)
    if hit then
      return hit
    end
    local turns
    if src.provider == "opencode" then
      turns = oc_json({ "--list", "--session", src.session }, vim.g.claude_reply_oc_list_cmd)
    else
      turns = src.path and M.all_replies(src.path) or nil
    end
    if turns then
      cache_put(turns_cache, key, turns)
    end
    return turns
  end
  if vim.b[buf].claude_reply_provider == "opencode" then
    return oc_json({ "--list" }, vim.g.claude_reply_oc_list_cmd)
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

-- picker-row highlight groups (default-linked: colorscheme-friendly,
-- user-overridable). re-applied on ColorScheme by setup_autocmds.
local function define_hls()
  local hl = vim.api.nvim_set_hl
  hl(0, "ClaudeReplyCc", { link = "Function", default = true })
  hl(0, "ClaudeReplyOc", { link = "String", default = true })
  hl(0, "ClaudeReplyDate", { link = "Comment", default = true })
  hl(0, "ClaudeReplyProj", { link = "Directory", default = true })
end
M.define_hls = define_hls

-- build a telescope display (text, highlights) pair from
-- { {chunk, hl_group|nil}, ... } segments (byte-indexed columns).
local function hl_display(segs)
  local text, hls, off = "", {}, 0
  for _, s in ipairs(segs) do
    text = text .. s[1]
    if s[2] then
      hls[#hls + 1] = { { off, off + #s[1] }, s[2] }
    end
    off = off + #s[1]
  end
  return text, hls
end

local function badge_hl(provider)
  return provider == "opencode" and "ClaudeReplyOc" or "ClaudeReplyCc"
end

-- first <C-c> clears the typed filter; a second (prompt now empty)
-- closes the picker.
local function map_clear_first_cc(map, prompt_bufnr)
  local actions = require("telescope.actions")
  local action_state = require("telescope.actions.state")
  local cc = function()
    if action_state.get_current_line() ~= "" then
      action_state.get_current_picker(prompt_bufnr):reset_prompt()
    else
      actions.close(prompt_bufnr)
    end
  end
  map("i", "<C-c>", cc)
  map("n", "<C-c>", cc)
end

-- month-day + time for session rows (turn rows use fmt_ts). handles
-- fs mtime (seconds) and opencode epoch-ms.
local function fmt_date(ts)
  if type(ts) ~= "number" then
    return "??-??"
  end
  if ts > 1e12 then
    ts = math.floor(ts / 1000)
  end
  return os.date("%m-%d %H:%M", ts)
end

-- pretty project label from a claude slug dir or an opencode
-- directory path: "-home-goodboy-repos-lns" / "/home/goodboy/repos/lns"
-- -> "repos/lns"
local function proj_label(s)
  s = s:gsub("^" .. vim.pesc(vim.env.HOME or ""), ""):gsub("^[-/]home[-/][^-/]+[-/]?", "")
  s = s:gsub("^[-/]+", ""):gsub("-", "/")
  return (s == "") and "~" or s
end

-- claude sessions: *.jsonl under the cwd slug dir (or, all_scope, the
-- newest 30 across every project slug). titles: LAST custom-title or
-- ai-title line, else LAST last-prompt line, else the uuid prefix —
-- extracted with two batched greps (2 shell-outs total, any file count).
local function claude_sessions(all_scope)
  local fs = vim.uv or vim.loop
  local dirs = {}
  if all_scope then
    local base = (vim.env.CLAUDE_CONFIG_DIR or (vim.env.HOME .. "/.claude")) .. "/projects"
    local h = fs.fs_scandir(base)
    while h do
      local name, t = fs.fs_scandir_next(h)
      if not name then
        break
      end
      if t == "directory" then
        dirs[#dirs + 1] = base .. "/" .. name
      end
    end
  else
    dirs = { transcript_dir() }
  end
  local files = {}
  for _, dir in ipairs(dirs) do
    for _, ent in ipairs(list_transcripts(dir)) do
      files[#files + 1] = { path = ent.path, ts = ent.mtime, proj = proj_label(vim.fn.fnamemodify(dir, ":t")) }
    end
  end
  table.sort(files, function(a, b)
    return a.ts > b.ts
  end)
  if all_scope and #files > 30 then
    for i = #files, 31, -1 do
      files[i] = nil
    end
  end
  if #files == 0 then
    return {}
  end
  -- batched title greps: last match per file wins
  local paths = {}
  for _, f in ipairs(files) do
    paths[#paths + 1] = f.path
  end
  local titles = {}
  local function harvest(pattern, tbl)
    local cmd = { "grep", "-aoHE", pattern }
    vim.list_extend(cmd, paths)
    for _, line in ipairs(vim.fn.systemlist(cmd)) do
      local p, val = line:match('^(.-):"[^"]+":"(.*)"$')
      if p and val then
        tbl[p] = val -- later lines overwrite: LAST occurrence wins
      end
    end
  end
  harvest('"(customTitle|aiTitle)":"[^"]*"', titles)
  local prompts = {}
  harvest('"lastPrompt":"[^"]*"', prompts)
  local out = {}
  for _, f in ipairs(files) do
    local title = titles[f.path] or prompts[f.path]
      or vim.fn.fnamemodify(f.path, ":t:r"):sub(1, 8)
    out[#out + 1] = {
      provider = "claude",
      path = f.path,
      title = title,
      ts = f.ts,
      proj = f.proj,
    }
  end
  return out
end

-- merged cross-harness session list, newest first (TTL-cached)
function M.list_sessions(all_scope)
  local ckey = all_scope and "all" or "cwd"
  local hit = cache_get(session_cache, ckey)
  if hit then
    return hit
  end
  local out = claude_sessions(all_scope)
  local extra = all_scope and { "--sessions", "--all-dirs" } or { "--sessions" }
  for _, s in ipairs(oc_json(extra, vim.g.claude_reply_oc_sessions_cmd) or {}) do
    out[#out + 1] = {
      provider = "opencode",
      session = s.id,
      title = (s.title and s.title ~= "") and s.title or s.id:sub(1, 12),
      ts = s.ts,
      proj = proj_label(s.directory or ""),
    }
  end
  table.sort(out, function(a, b)
    local ta = (a.ts or 0) > 1e12 and (a.ts / 1000) or (a.ts or 0)
    local tb = (b.ts or 0) > 1e12 and (b.ts / 1000) or (b.ts or 0)
    return ta > tb
  end)
  return cache_put(session_cache, ckey, out)
end

-- `src` (optional) targets another session's turns; `nav` (optional,
-- {scope=<bool>, query=<string>}) marks arrival FROM the dialog picker
-- — enables <C-o> back-navigation that restores its scope AND typed
-- filter query.
function M.pick_reply(buf, src, nav)
  buf = buf or vim.api.nvim_get_current_buf()
  local turns = fetch_turns(buf, src)
  if not turns or #turns == 0 then
    warn("no prior replies found for this session")
    return
  end
  local label = src and src.title or nil
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
      prompt = label and ("replies · " .. label) or "prior AI replies",
      format_item = function(it)
        return it.label
      end,
    }, function(choice)
      if choice then
        M.set_reference(buf, choice.text, choice.idx, choice.total, label)
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
      prompt_title = (label and ("replies · " .. label) or "prior AI replies")
        .. " · <CR> page · <C-q> quote"
        .. (nav ~= nil and " · <C-o> back" or ""),
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
            M.set_reference(buf, e.value.text, e.value.idx, e.value.total, label)
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
        if nav ~= nil then
          local back = function()
            actions.close(prompt_bufnr)
            -- restore the dialog picker with its scope AND the query
            -- that was typed there before drilling in (scheduled:
            -- same-tick reopen leaks the trigger key into the prompt)
            vim.schedule(function()
              M.pick_session(buf, nav.scope, nav.query)
            end)
          end
          map("i", "<C-o>", back)
          map("n", "<C-o>", back)
        end
        map_clear_first_cc(map, prompt_bufnr)
        return true
      end,
    })
    :find()
end

-- dialog rows, either flat (newest-first) or GROUPED by project dir:
-- parent groups ordered by their most-recent dialog, children
-- newest-first inside. group headers are telescope-only pseudo-rows
-- with an EMPTY ordinal — visible while the prompt is empty (the
-- "tree" view), gone the instant you type (flat fuzzy takes over;
-- telescope has no real tree, this is the idiomatic fake).
local function dialog_items(sessions, grouped)
  local function row(s, indent)
    local badge = s.provider == "opencode" and "oc" or "cc"
    local segs = {
      { indent .. "[" .. badge .. "]", badge_hl(s.provider) },
      { " " .. fmt_date(s.ts), "ClaudeReplyDate" },
      { "  " .. vim.fn.strcharpart(s.title or "", 0, 48) },
    }
    if not grouped then
      segs[#segs + 1] = { "  (" .. (s.proj or "?") .. ")", "ClaudeReplyProj" }
    end
    local text = ""
    for _, seg in ipairs(segs) do
      text = text .. seg[1]
    end
    return { src = s, segs = segs, label = text }
  end
  local items = {}
  if not grouped then
    for _, s in ipairs(sessions) do
      items[#items + 1] = row(s, "")
    end
    return items
  end
  -- sessions arrive newest-first, so first-appearance order of each
  -- proj == MRU order of the groups
  local groups, order = {}, {}
  for _, s in ipairs(sessions) do
    local k = s.proj or "?"
    if not groups[k] then
      groups[k] = {}
      order[#order + 1] = k
    end
    table.insert(groups[k], s)
  end
  for _, k in ipairs(order) do
    items[#items + 1] = {
      header = true,
      label = "(" .. k .. ")",
      segs = { { "(" .. k .. ")", "ClaudeReplyProj" } },
    }
    for _, s in ipairs(groups[k]) do
      items[#items + 1] = row(s, "  ")
    end
  end
  return items
end

-- stage 1: fuzzy-pick a DIALOG/session (both harnesses merged,
-- colorized [cc]/[oc] badges), then drill into its turns. `all_scope`
-- widens from the cwd project to every project/directory (<C-a>
-- toggles it live, keeping the typed query). `default_text` pre-fills
-- the fuzzy prompt (used by <C-o> back-nav query retention). the view
-- is GROUPED by project dir by default (g:claude_reply_dialogs_grouped
-- = false, or <C-t> live, for flat newest-first).
function M.pick_session(buf, all_scope, default_text, flat)
  buf = buf or vim.api.nvim_get_current_buf()
  all_scope = all_scope or false
  if flat == nil then
    flat = vim.g.claude_reply_dialogs_grouped == false
  end
  local sessions = M.list_sessions(all_scope)
  if #sessions == 0 then
    warn(all_scope and "no sessions found anywhere" or "no sessions for this project (try <C-a> for all)")
    return
  end
  local items = dialog_items(sessions, not flat)
  -- the scope tag shows the ACTUAL project dir, not the word "pwd"
  local scope_tag = all_scope and "⟦ALL⟧" or ("⟦" .. proj_label(vim.fn.getcwd()) .. "⟧")

  local has_telescope, pickers = pcall(require, "telescope.pickers")
  if not has_telescope then
    -- headers are telescope-only sugar: flat list for the fallback
    local flat_items = {}
    for _, it in ipairs(items) do
      if not it.header then
        flat_items[#flat_items + 1] = it
      end
    end
    vim.ui.select(flat_items, {
      prompt = scope_tag .. " AI dialogs",
      format_item = function(it)
        return it.label
      end,
    }, function(choice)
      if choice then
        M.pick_reply(buf, choice.src, { scope = all_scope, query = "" })
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
      prompt_title = scope_tag .. " AI dialogs · <C-a> scope · <C-g> deep · <C-t> tree/flat",
      default_text = default_text,
      finder = finders.new_table({
        results = items,
        entry_maker = function(it)
          return {
            value = it,
            display = function()
              return hl_display(it.segs)
            end,
            -- group headers get an EMPTY ordinal: they never match a
            -- typed query, so the "tree" collapses to flat fuzzy the
            -- moment you start filtering
            ordinal = it.header and "" or it.label,
          }
        end,
      }),
      sorter = tconf.generic_sorter({}),
      previewer = previewers.new_buffer_previewer({
        title = "last reply",
        define_preview = function(self, entry)
          if entry.value.header then
            vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, { entry.value.label })
            return
          end
          -- fetch_turns is TTL-cached for src fetches: hover spam is ok
          local turns = fetch_turns(buf, entry.value.src)
          local text = (turns and #turns > 0) and turns[#turns].text or "(no replies)"
          vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, vim.split(text, "\n", { plain = true }))
          pcall(function()
            vim.bo[self.state.bufnr].syntax = "markdown"
          end)
        end,
      }),
      attach_mappings = function(prompt_bufnr, map)
        -- NB every close->reopen hop is vim.schedule()d: opening the
        -- next picker in the same tick lets the tail of the trigger
        -- key leak into the new prompt (the "stray G" bug)
        actions.select_default:replace(function()
          local e = action_state.get_selected_entry()
          local q = action_state.get_current_line()
          actions.close(prompt_bufnr)
          if e and e.value.header then
            return -- group headers aren't openable
          end
          if e then
            vim.schedule(function()
              M.pick_reply(buf, e.value.src, { scope = all_scope, query = q })
            end)
          end
        end)
        local toggle = function()
          local q = action_state.get_current_line()
          actions.close(prompt_bufnr)
          vim.schedule(function()
            M.pick_session(buf, not all_scope, q, flat)
          end)
        end
        map("i", "<C-a>", toggle)
        map("n", "<C-a>", toggle)
        local treeflat = function()
          local q = action_state.get_current_line()
          actions.close(prompt_bufnr)
          vim.schedule(function()
            M.pick_session(buf, all_scope, q, not flat)
          end)
        end
        map("i", "<C-t>", treeflat)
        map("n", "<C-t>", treeflat)
        local deep = function()
          local q = action_state.get_current_line()
          actions.close(prompt_bufnr)
          vim.schedule(function()
            M.pick_deep(buf, all_scope, { query = q })
          end)
        end
        map("i", "<C-g>", deep)
        map("n", "<C-g>", deep)
        map_clear_first_cc(map, prompt_bufnr)
        return true
      end,
    })
    :find()
end

-- ── deep content search: fuzzy over EVERY turn's full text ─────────

-- flat cross-session turn corpus for `all_scope`; optionally
-- pre-filtered by `pat` (case-insensitive substring). claude side
-- parses each session's jsonl (grepper-narrowed when `pat` given);
-- opencode side is one `--dump`/`--grep` extractor spawn.
local function deep_rows(all_scope, pat)
  local rows = {}
  local needle = pat and pat:lower() or nil
  -- opencode
  local extra = pat and { "--grep", pat } or { "--dump" }
  if all_scope then
    extra[#extra + 1] = "--all-dirs"
  end
  for _, ses in ipairs(oc_json(extra, vim.g.claude_reply_oc_dump_cmd) or {}) do
    local total = #ses.turns
    for i, t in ipairs(ses.turns) do
      rows[#rows + 1] = {
        provider = "opencode",
        title = (ses.title and ses.title ~= "") and ses.title or (ses.id or "?"):sub(1, 12),
        proj = proj_label(ses.directory or ""),
        idx = i,
        total = total,
        text = t.text,
      }
    end
  end
  -- claude: with a pattern, narrow candidate files first via the
  -- configured grepper (g:claude_reply_grepper; rg when available)
  local csessions = claude_sessions(all_scope)
  if needle and #csessions > 0 then
    local grepper = vim.g.claude_reply_grepper
      or (vim.fn.executable("rg") == 1 and "rg" or "grep")
    local cmd = { grepper, "-l", "-i" }
    if grepper ~= "rg" then
      cmd[#cmd + 1] = "-a"
    end
    cmd[#cmd + 1] = "--"
    cmd[#cmd + 1] = pat
    for _, s in ipairs(csessions) do
      cmd[#cmd + 1] = s.path
    end
    local matched = {}
    for _, p in ipairs(vim.fn.systemlist(cmd)) do
      matched[p] = true
    end
    local kept = {}
    for _, s in ipairs(csessions) do
      if matched[s.path] then
        kept[#kept + 1] = s
      end
    end
    csessions = kept
  end
  for _, s in ipairs(csessions) do
    local turns = fetch_turns(nil, { provider = "claude", path = s.path, title = s.title })
    if turns then
      local total = #turns
      for i, t in ipairs(turns) do
        if not needle or t.text:lower():find(needle, 1, true) then
          rows[#rows + 1] = {
            provider = "claude",
            title = s.title,
            proj = s.proj,
            idx = i,
            total = total,
            text = t.text,
          }
        end
      end
    end
  end
  return rows
end

-- turn-level fuzzy picker across ALL scoped sessions: the `ordinal`
-- carries each turn's FULL text, so typing fuzzes reply CONTENT
-- cross-project/cross-harness. opts = { query=<prefill>, pat=<plain
-- substring pre-filter (from :ClaudeReplyGrep)> }.
function M.pick_deep(buf, all_scope, opts)
  buf = buf or vim.api.nvim_get_current_buf()
  opts = opts or {}
  local rows = deep_rows(all_scope, opts.pat)
  if #rows == 0 then
    warn(opts.pat and ("no replies match '" .. opts.pat .. "'") or "no replies found")
    return
  end
  local items = {}
  for _, r in ipairs(rows) do
    local badge = r.provider == "opencode" and "oc" or "cc"
    local segs = {
      { "[" .. badge .. "]", badge_hl(r.provider) },
      { " " .. vim.fn.strcharpart(r.title or "?", 0, 24), "ClaudeReplyProj" },
      { (" #%d/%d"):format(r.idx, r.total), "ClaudeReplyDate" },
      { "  " .. first_line(r.text) },
    }
    local text = ""
    for _, seg in ipairs(segs) do
      text = text .. seg[1]
    end
    items[#items + 1] = { row = r, segs = segs, label = text }
  end
  local scope_tag = all_scope and "⟦ALL⟧" or "⟦pwd⟧"
  local title = scope_tag
    .. " deep reply search"
    .. (opts.pat and (" /" .. opts.pat .. "/") or "")
    .. " · <CR> page · <C-q> quote · <C-o> dialogs"

  local has_telescope, pickers = pcall(require, "telescope.pickers")
  if not has_telescope then
    vim.ui.select(items, {
      prompt = title,
      format_item = function(it)
        return it.label
      end,
    }, function(choice)
      if choice then
        local r = choice.row
        M.set_reference(buf, r.text, r.idx, r.total, r.title)
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
      prompt_title = title,
      default_text = opts.query,
      finder = finders.new_table({
        results = items,
        entry_maker = function(it)
          return {
            value = it,
            display = function()
              return hl_display(it.segs)
            end,
            -- deep: full turn text drives the fuzzy match
            ordinal = it.label .. " " .. it.row.text,
          }
        end,
      }),
      sorter = tconf.generic_sorter({}),
      previewer = previewers.new_buffer_previewer({
        title = "reply",
        define_preview = function(self, entry)
          vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, vim.split(entry.value.row.text, "\n", { plain = true }))
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
            local r = e.value.row
            M.set_reference(buf, r.text, r.idx, r.total, r.title)
          end
        end)
        local quote = function()
          local e = action_state.get_selected_entry()
          actions.close(prompt_bufnr)
          if e then
            M.pull_section(buf, vim.split(e.value.row.text, "\n", { plain = true }))
          end
        end
        map("i", "<C-q>", quote)
        map("n", "<C-q>", quote)
        local back = function()
          local q = action_state.get_current_line()
          actions.close(prompt_bufnr)
          vim.schedule(function()
            M.pick_session(buf, all_scope, q)
          end)
        end
        map("i", "<C-o>", back)
        map("n", "<C-o>", back)
        map_clear_first_cc(map, prompt_bufnr)
        return true
      end,
    })
    :find()
end

-- :ClaudeReplyGrep {pat} — external-grepper-backed content search
-- (rg by default, g:claude_reply_grepper to choose); bang == all
-- projects. results land in the deep picker for further fuzzing.
function M.grep_replies(buf, pat, all_scope)
  if not pat or pat == "" then
    warn("grep: give me a pattern")
    return
  end
  M.pick_deep(buf, all_scope or false, { pat = pat })
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
  define_hls()
  vim.api.nvim_create_autocmd("ColorScheme", {
    group = grp,
    callback = define_hls,
  })
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
