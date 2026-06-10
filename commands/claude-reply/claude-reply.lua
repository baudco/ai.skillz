-- claude-reply.lua
--
-- Augment Claude Code's external-editor temp buffer
-- (`claude-prompt-*.md`, opened on Ctrl-G when `externalEditorContext`
-- is on) with an email-style quote-reply workflow.
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
local HEAD_TXT = "Claude's last response"

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

  strip_reference(buf, mk)
  apply_view_opts()
  apply_folds(buf, mk)
  ensure_highlight(buf)
  setup_colorscheme(buf)

  local park = math.min(mk.reply + 1, vim.api.nvim_buf_line_count(buf))
  vim.api.nvim_win_set_cursor(0, { park, 0 })

  setup_maps(buf)
end

function M.setup_autocmds()
  local grp = vim.api.nvim_create_augroup("ClaudeReply", { clear = true })
  vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter" }, {
    group = grp,
    pattern = "claude-prompt-*.md",
    callback = function(ev)
      local buf = ev.buf
      if vim.b[buf].claude_reply_ready then
        -- re-shown in a new window (split): re-assert window-local view
        local mk = M.find_markers(buf)
        if mk.reply then
          apply_view_opts()
          apply_folds(buf, mk)
          ensure_highlight(buf)
        end
        return
      end
      M.setup_buffer(buf)
    end,
  })
end

package.loaded["claude_reply"] = M
M.setup_autocmds()

return {}
