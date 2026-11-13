---
name: lua-codestyle
description: >
  Required Lua authoring and readability conventions. Use before writing,
  editing or proposing Lua code, including Neovim plugins, configuration,
  tests and snippets, and when reviewing those changes for readability.
compatibility: >
  Any agent with repository file access. No formatter installation needed.
metadata:
  author: goodboy
  version: "0.1"
---

# Lua code style

Make inputs, values and nesting independently scannable. This skill
owns Lua authoring rules; it does not change program behavior or
provide a formatter, test runner or blocking enforcement hook.

## Required authoring and handoff gate

- Read this skill in full before authoring Lua. Use the project's
  selected guide and explicit overrides; report missing or divergent
  guidance instead of silently substituting another version.
- Apply the rules to new/changed implementation, helpers, fixtures,
  tests and review snippets. Preserve verbatim quotations of evidence.
- Before handoff, inspect the actual changed source against the whole
  guide. A passing formatter or test suite is not a readability pass.
- Fix violations in authorized edits; a read-only review reports them
  instead. Disclose uninspected scope and unavailable checks.
- Preserve maintainer comments, rationale and disabled experiments.
  Do not change user-owned task/checklist states or restyle unrelated
  providers merely because their code is nearby.

## Expanded tables: one entry per line

- Once a table uses multiline layout, put each field or array entry
  on its own line. Do not pack several entries onto continuation
  lines just because they fit the width limit.
- Use the same rule for returned records, options, cache keys, argv
  lists and test fixtures. Keep nested table values visibly nested.
- Align the closing delimiter with the statement that opens the
  structure. Follow the project's trailing-comma convention for
  table fields; a trailing comma is useful for additions and diffs.
- Genuinely small, simple tables may stay inline, such as `{}`,
  `{ "--list" }` or `{ enabled = true }`. Do not expand a tiny leaf
  merely because its parent call is multiline.
- Follow explicit project indentation, quote and line-width rules.
  Examples here use two spaces and double quotes. Width compliance
  alone is not a reason to keep a crowded structure inline.

```lua
local function pi_context(session)
  if not session.session_store then return nil end
  return {
    id = session.id,
    path = session.path,
    directory = session.directory,
    session_store = session.session_store,
    session_layout = session.session_layout,
  }
end
```

Do not compress that returned record into multiple fields per line.
The surrounding table is already expanded; the fields are its units
of information.

## Crowded calls: one argument per line

- Expand long or structurally crowded calls: several nested values,
  callbacks or tables can require expansion even below the width
  limit. Make the argument list distinguishable from each value.
- In an expanded call, put each argument on its own line. A nested
  table or callback occupies an indented block rather than being
  flattened into the surrounding argument list.
- Put the closing delimiter on its own line, aligned with the call's
  opening statement. Idiomatic combined closers such as `})` and
  `end)` may remain intact when they clearly close the same value.
- Do not add a trailing comma after the final function argument;
  Lua permits trailing commas in tables, not argument lists.
- Short, simple calls such as `resume(session.id)` may stay inline.
  Do not wrap every call mechanically or invent locals just to make
  a compact call look smaller.

```lua
vim.api.nvim_buf_set_var(
  buf,
  "ai_reply_pi_context",
  {
    id = session.id,
    path = session.path,
    directory = session.directory,
  }
)
```

A table argument can use the project's idiomatic `call({ ... })`
form too; its expanded fields still belong on separate lines.

## Named inputs for complex APIs

- Prefer a documented options table for project-owned complex or
  non-obvious routines, especially when several positional values,
  booleans, optional controls or callbacks obscure their meanings.
- Lua has no native keyword-call syntax. A call such as
  `calculateArea(type='Rect', length=2, width=4)` is invalid Lua;
  field names belong inside a table argument instead.
- Follow the API's real signature. Keep established positional
  calls for builtins, Neovim and third-party functions; do not wrap
  their arguments in a table unless the API accepts one.
- For fixed positional APIs, make unclear inputs readable through
  useful named locals, expanded arguments or a concise explanation.
  Do not invent wrappers solely to imitate keyword arguments.
- Keep short, self-evident positional calls compact. Converting an
  existing positional API to an options table is a contract change,
  not a layout-only edit: obtain authorization and update callers.

```lua
calculateArea({
  type = "Rect",
  length = 2,
  width = 4,
})
```

## Compound conditions

- For an `if` condition combining operands with `and` or `or`, use
  multiline parentheses with each operand and each connective on
  its own line, even when the condition fits the width limit.
- Apply the same layout to compound `elseif`, `while` and `until`
  conditions. Put `then` or `do` beside the closing parenthesis.
- Preserve grouping, evaluation order and short-circuit behavior;
  layout must not change which calls execute or which values flow.
- This rule concerns conditions, not every value expression. Short
  fallback values such as `session.path or ""` may remain inline.

```lua
if (
  src.provider == "pi"
  and
  src.context
) then
  key = table.concat(
    {
      key,
      src.context.session_store or "",
      src.context.session_layout or "",
      src.context.path or "",
      src.context.directory or "",
    },
    "\0"
  )
end
```

## Branches, closures and explanations

- Lua's `end` already marks scope closure. Do not mechanically import
  Python's occupied-column scope-gap rule or add blank lines after
  every `end`. Separate distinct logical phases when useful.
- Tiny, single-condition guards may stay inline, as in `pi_context()`.
  Expand nontrivial branches and callback bodies so conditions,
  effects and closure ownership can be read independently.
- Keep comments with the code they explain. Name concrete functions,
  fields and owners instead of ambiguous references to a cache,
  context or record. Keep useful implementation rationale nearby.
- Describe nontrivial contracts with an operation-first summary and
  purpose-grouped bullets: inputs/selection, outputs, side effects,
  failures and caller responsibilities. A simple helper may need
  only its opening sentence; follow the project's Lua comment style.
- Explain regression failure mechanisms, triggering conditions and
  what the assertions prove. Formatting must not erase that proof.

## Preserve Lua semantics while changing layout

- Keep evaluation order, table entry order and callback behavior.
  Do not rewrite control flow as a side effect of formatting.
- Preserve method `:` versus function `.` calls, varargs and multiple
  return behavior. Adding parentheses can change how many values a
  call contributes; do not introduce them merely to wrap a line.
- Preserve string/long-bracket literal contents and metamethod or
  lifecycle behavior. Do not add runtime dependencies or annotations
  solely to enforce presentation.

## Verification

- Inspect every expanded table/call, including fixtures, for packed
  entries or arguments and ambiguous closing-delimiter alignment.
- Check compound conditions for standalone connective lines and
  complex APIs for meaningful, signature-correct input names.
- Use existing, authorized project syntax checks, formatters in
  check-only mode and tests. Do not install tools or apply a broad
  formatter configuration without authorization.
- For layout-only changes, compare non-debug bytecode when an
  existing compatible Lua compiler is available and execution is
  authorized. Treat equality as useful evidence, not a replacement
  for source review or tests; debug locations can still change.
- Report which files were inspected, which checks ran and which were
  unavailable. Do not claim every agent is mechanically constrained
  merely because this skill is discoverable.
