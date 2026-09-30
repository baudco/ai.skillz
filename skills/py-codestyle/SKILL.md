---
name: py-codestyle
description: >
  Required Python and Xonsh authoring conventions. Use before writing,
  editing or proposing Python/Xonsh code, including tests and snippets,
  and when checking those changes for readability.
compatibility: >
  Language-agnostic agent. No external tools needed.
metadata:
  author: goodboy
  version: "0.1"
---

# Python code style guide

These rules apply globally to ALL python projects.

## Required authoring and handoff gate

- Read this skill in full before writing, editing or proposing Python
  or Xonsh code. Apply it to implementation, helpers, tests, comments,
  docstrings and newly authored review snippets; no separate review
  invocation is required. Preserve verbatim quotations of evidence.
- Before handoff, inspect every new or changed Python/Xonsh scope
  against the complete guide. Review the actual source, not merely
  formatter/linter output or the fact that a skill was discovered.
- Check contract/proof bullets, symbol references, concrete types,
  named policy bounds, contextual errors, multiline/boolean shapes,
  occupied-column scope gaps and preserved maintainer context.
- Correct violations in authorized edits before calling them ready.
  A read-only review instead reports them without modifying files.
  Disclose uninspected scope, unresolved violations and unavailable
  checks; never equate passing tests with a completed style pass.

## Review lessons

For concurrent/runtime test code and review remediation, read
[the shared review lessons](references/review-lessons.md). Also read
`<repo-root>/.ai/py-codestyle/review-lessons.md` when present.
Resolve that optional project reference from the active worktree,
not from this skill's deployment directory. It adds local examples
and conventions; the shared rules and user authorization prevail
where instructions conflict. Never import another project's file.

## Preserve maintainer context

- Treat comments, TODOs, FIXMEs, disabled experiments,
  commented-out options, and rationale notes as maintained
  project content, not cleanup opportunities.
- When refactoring nearby code, move still-relevant notes
  with the code they describe. Preserve their wording and
  task/checklist markers unless the requested change needs a
  wording update.
- Delete or rewrite a note only when the current patch
  demonstrably resolves it, makes it factually obsolete, or
  replaces it with equivalent or better documentation.
- A changed code shape, cleaner-looking block, linter pass, or
  personal uncertainty about a note is NOT sufficient reason
  to remove it. Preserve it or ask the human.
- Never change `[ ]`, `[x]`, TODO/WIP/DONE, or similar state
  markers unless the human explicitly requests that exact
  state transition.
- During final diff review, account for every removed comment
  or TODO. Restore any removal that is not directly justified
  by the patch's behavior.

## Namespace-qualified technical prose

- In Python comments and docstrings, qualify implementation
  nouns such as "table", "registry", "mapping", "index", and
  "cache" with the exact declaring symbol on first reference.
  For example: canonical SID registry
  (`Runspace._sid2spawn`) or graphical refs (`Wks.wins`).
- Prefer class/field paths which support symbol lookup, such as
  `Spawn.sub_spawns` and `Spawn.win_ids2sub_sids`, over vague
  phrases such as "parent-local indexes" or "this mapping".
- When describing an instance-specific operation, name both the
  concrete expression and its declaring field. For example,
  `tuple(spawn.sub_spawns.values())` snapshots the current
  instance's `Spawn.sub_spawns` mapping.
- Name the exact method which mutates a registry and the exact
  fields it can mutate. Do not say "normal cleanup clears every
  index" when `Runspace.pub_spawn_end()` and the affected fields
  can be named directly.
- Re-qualify a symbol later when intervening prose introduces
  another plausible table or owner. Optimize comments and
  regression docstrings for editor symbol lookup, not only for a
  reader who already holds the full runtime model in memory.

## Concrete contracts and policy

- Type concrete inputs, callbacks and records. Explain unavoidable
  dynamic boundaries, including raw external data; do not use `Any`
  as a substitute for understanding and validating consumed fields.
- Name constants for policy limits and include their units. Explain
  non-obvious algorithms, failure boundaries and external parser,
  completer or lifecycle hooks beside the relevant implementation.
- Error messages identify the rejected values and operation, harness
  or dialog. Quote or escape untrusted values so diagnostics remain
  unambiguous and terminal-safe; do not expose secrets.
- Compatibility branches need an evidenced consumer or supported
  data format. Do not invent obsolete project aliases defensively.

## Line length

- **69 char max per source line** including
  indentation, quotes, and all syntax.
- This applies to code, comments, docstrings, and
  string literals alike.
- For multiline string literals (log msgs, error
  msgs, `print()` calls), pack each source line
  close to 69 chars. Don't break too early just
  because of `\n` boundaries in rendered output —
  use the full width available after indent + quoting.
- When a string line has an f-string interpolation
  that makes length variable, it's fine to split at
  that boundary but keep the continuation packed too.
- Where the 69 char limit would be violated, convert
  to a multiline style matching surrounding similar
  syntax uses in the current code base.

## Strings

- Prefer `'` single quotes for literal strings
  over `"`.
- Never use f-strings without substitution vars;
  use regular strings to avoid `ruff` F541 warnings.
- If ANY single line in a multi-line implicit string
  concat uses f-string syntax, ensure ALL following
  lines in the same literal are also prefixed with
  `f'` to maintain left-alignment.
- When a string literal contains a double newline
  (`\n\n`), always split so the second `\n` starts
  its own source line. This makes the code visually
  mirror the rendered output — each blank line in the
  output maps to a standalone `\n` in the source:

  ```python
  # GOOD - double newline split across lines
  log.warning(
      f'Failed to resolve type via\n'
      f'`mod.get_type()`:\n'
      f'\n'
      f'`{type_name}` is not registered!\n'
  )

  # BAD - \n\n jammed onto one line
  log.warning(
      f'Failed to resolve type via\n'
      f'`mod.get_type()`:\n\n'
      f'`{type_name}` is not registered!\n'
  )
  ```

- For `print()`/`log.*()` calls, use a SINGLE call
  with multiline string content and `\n` chars,
  NEVER multiple `print()` calls per line:

  ```python
  # GOOD
  print(
      f'To generate commit message:\n'
      f'  cat {args.output} | <your-tool>\n'
  )

  # BAD - never do this
  print("To generate commit message:")
  print(f"  cat {args.output} | <your-tool>")
  ```

- Pre-assign any value injected via an f-string to a
  named local FIRST, then reference that name from
  inside the literal. Two reasons: (1) easier to
  inspect at a breakpoint or log-line edit since
  the value has a name, (2) avoids embedding
  comprehensions / `'\n'.join(...)` mid-literal which
  break the implicit concat AND scatter F541 warnings
  on the trailing `f'...'` lines that lose their
  contiguity with substitution-bearing lines:

  ```python
  # GOOD - join pre-extracted, single implicit-concat
  mismatch_lines: str = '\n'.join(
      f'  - proto_key={pk!r}  addr={a!r}'
      for pk, a in bad_addrs
  )
  raise ValueError(
      f'`registry_addrs` contains addr(s) whose proto is '
      f'not in `enable_transports`!\n'
      f'enable_transports: {enable_transports!r}\n'
      f'mismatched_addrs:\n'
      f'{mismatch_lines}\n'
      f'\n'
      f'Either add the missing proto to '
      f'`enable_transports`, or remove the addr from '
      f'`registry_addrs`.'
  )

  # BAD - join inlined, breaks implicit concat
  raise ValueError(
      f'`registry_addrs` contains addr(s) whose proto is '
      f'not in `enable_transports`!\n'
      f'enable_transports: {enable_transports!r}\n'
      f'mismatched_addrs:\n'
      + '\n'.join(
          f'  - proto_key={pk!r}  addr={a!r}'
          for pk, a in bad_addrs
      )
      + '\n\n'
      f'Either add the missing proto to '   # F541!
      f'`enable_transports`, or remove the '  # F541!
      f'addr from `registry_addrs`.'          # F541!
  )
  ```

## Docstrings

- Always use `'''` (single-quote triple) with this
  multiline style for all `def` and `class` blocks:

  ```python
  def some_func():
      '''
      Summary line here.

      - Inputs/selection: describe accepted values and scope.
      - Outputs: describe the caller-visible result.

      '''
  ```

  Rules:
  * first line contains ONLY `'''` + newline
  * content follows std PEP guidelines
  * final 2 lines: a blank line, then closing `'''`

- Open with one sentence naming the operation and its role.
- A simple function may need only that opening sentence.
- For several behaviors, follow the summary with compact bullets
  grouped by purpose: inputs/selection, outputs, side effects,
  failures and caller contracts. Include only relevant groups.
- Keep one behavior per bullet and name the actual fields and
  functions. Prefer a quick high-level scan over dense prose that
  merely contains all the information.
- Explain non-obvious implementation reasons beside the relevant
  code, rather than burying them in a contract summary.
- Regression bullets must retain the failure mechanism, triggering
  conditions and proof required by the next section; bullet layout
  does not replace that explanation.

## Regression test documentation

- Every newly added regression test MUST have a detailed
  docstring which preserves the reason the test exists.
- The docstring must explain:
  * the original failure mode or incorrect behavior;
  * the triggering input, state, or task/event
    interleaving;
  * the invariant or user-visible behavior which was
    violated;
  * how the test arranges the reproducing conditions;
  * how its synchronization and assertions prove the fix.
- For concurrency or race regressions, name the relevant
  tasks, events, cancellation points, or publication order.
  Explain why the test controls that ordering
  deterministically instead of depending on timing luck.
- Do not merely restate the test name or narrate each code
  statement. Capture the failure mechanism and the proof
  boundary so future maintainers can distinguish required
  behavior from incidental test implementation.
- Existing non-regression tests do not need expanded
  docstrings unless they are being materially rewritten to
  audit a specific prior bug.

## Type annotations

- Declare a local's type immediately before a control-flow statement
  which binds its runtime value. Apply this to `for` targets, tuple
  unpacking, comprehensions, and `with` / `async with` targets, where
  the annotation cannot be written on the binding itself:

  ```python
  # GOOD - declaration precedes runtime binding
  bstream: BroadcastReceiver
  async with stream.subscribe() as bstream:
      msg: dict[str, Any]
      async for msg in bstream:
          await consume(msg)

  streams: tuple[BroadcastReceiver, ...]
  async with gather_contexts(mngrs) as streams:
      ...

  # BAD - annotation follows the runtime binding
  async with stream.subscribe() as bstream:
      bstream: BroadcastReceiver
      ...
  ```

- For ordinary local assignments and helper calls, keep the type and
  value in ONE annotated assignment. Do not split them into adjacent
  declaration and assignment statements. With multiline types, keep
  `] = value` or `) = value` together on the final type line whenever
  it fits:

  ```python
  # GOOD - one static declaration + runtime assignment
  broker: str = flume.mkt.broker
  local_feed: Feed = copy(feed)
  broker2bstreams: dict[
      str,
      BroadcastReceiver,
  ] = {}

  # BAD - avoid splitting ordinary assignments
  broker2bstreams: dict[
      str,
      BroadcastReceiver,
  ]
  broker2bstreams = {}
  ```

- No whitespace in union-style type annotations:
  `str|None` not `str | None`.
- When a union expression exceeds 69 chars, use
  multiline style:

  ```python
  type Keys = (
      str
      |int
      |UUID
      |None
  )
  ```

## Tuple unpacking

- When unpacking tuples with N > 2 elements, always
  use multiline style:

  ```python
  (
      var1,
      var2,
      var3,
  ) = some_tuple
  ```

## Exception handling

- When catching a tuple of multiple exception types,
  always use the multiline tuple style — one type
  per line, even when the line would fit. Makes diffs
  cleaner when adding/removing types and matches the
  surrounding multi-line tuple convention:

  ```python
  # GOOD
  try:
      ...
  except (
      FileNotFoundError,
      PermissionError,
      ProcessLookupError,
  ):
      ...

  # BAD — single-line tuple even when it fits
  except (FileNotFoundError, PermissionError, ProcessLookupError):
      ...
  ```

- A single exception type on one line is fine
  (`except OSError:`) — the rule kicks in only when
  the `except` clause catches a *tuple* of types.

## Boolean & branch expressions

- A flat chain of simple predicates using only `and` or only
  `or` may stay compact when it fits within 69 characters.
  When it wraps, put each next connective and predicate on one
  line when that line fits. Keep the original evaluation order.
- For mixed `and` and `or`, or nested compound operands, use
  parentheses to make grouping explicit. Put each top-level
  connective on its own line between its operand groups.
  Format nested compound groups the same way when they wrap.
- The same rules apply to `if`/`elif`/`while`/`assert`
  conditions and booleans assigned to named locals.

  ```python
  # GOOD - flat, simple predicates with one connective
  if ready and channel_open:
      ...

  if (
      ctx.chan is chan
      and ctx.side == 'parent'
      and ctx._scope is not None
      and ctx._status._remote_error is None
      and ctx._status._outcome_is_unfinished()
  ):
      ...

  # GOOD - mixed connectives with explicit grouping
  if (
      ready
      or
      (
          retry_allowed
          and
          channel_open
      )
  ):
      ...

  # BAD - mixed connectives obscure grouping
  if ready or retry_allowed and channel_open:
      ...
  ```

## Re-exports from `__init__` modules

- Use `import X as X` to mark a name as an
  intentional public re-export:

  ```python
  # GOOD - explicit re-export (PEP 484 convention)
  from ._submod import (
      some_func as some_func,
  )

  # BAD - `__all__` is a different concern
  # (controls `from pkg import *` only)
  from ._submod import some_func
  __all__ = ['some_func']

  # BAD - noqa hides intent
  from ._submod import some_func  # noqa
  ```

- This is the modern convention recognized by
  type checkers (pyright/mypy) to distinguish
  public API from internal imports.

## Whitespace

- Never write lines containing only whitespace;
  use a bare carriage return (empty line) instead.

### Vertical space at scope boundaries

Apply these rules to exits from every indented block:

- `if` / `elif` / `else` branches;
- `for` / `async for` and `while` loops, including loop `else`;
- `with` / `async with` context-manager bodies;
- `try` / `except` / `else` / `finally` clause bodies;
- `match` / `case` bodies;
- nested/embedded `def` / `async def` and `class` bodies, only where
  normal definition-spacing rules do not already decide the gap.

Normal definition spacing takes precedence: two blank lines at
module level, and one between methods.

Apply the following rules in order at a genuine scope exit.
A standalone closing delimiter is a line containing only `)`, `]`
or `}`, apart from indentation/trailing whitespace. Combined closers,
inline comments and code ending in a delimiter do not qualify.
A single-line body has one nonblank physical source line, including
comments; one statement wrapped across lines is not single-line.

1. **Matching `except`/`finally`:** omit the gap iff the preceding
   clause body is single-line or ends with a standalone closing
   delimiter. Otherwise, insert one blank line. This rule applies
   only when the next nonblank source line is itself the matching
   clause header; do not skip comments to find a later header.
2. **Standalone closing delimiter before other source:** insert one
   blank line when the next line has the same indentation or is one
   indentation level shallower than the delimiter line. A deeper
   dedent does not itself force a gap; apply rule 3 instead.
3. **Otherwise:** insert one blank line iff the terminating line and
   the next dedented nonblank source line occupy any common
   non-whitespace column. No overlap means no additional gap.

- Include comment text in the occupied columns; do not skip comments
  when finding the following source line. If a comment introduces
  the next statement, put the separating gap before that comment,
  keeping the comment attached to the statement it explains.

  ```python
      except ValueError:
          continue

      # JS treats [] and {} as truthy, unlike Python.
      if isinstance(value, dict):
          consume_record(value)
  ```

- Apply the ordinary overlap rule before other following clauses,
  including `elif` and `else`. Do not infer gaps from exit statements
  or body density beyond the explicit exceptions above.
- One blank line can delimit several scopes ending together. Do not
  treat wrapped expressions as scopes or add a gap after a block
  header. Retain normal spacing between function/class definitions;
  no following code means no additional end-of-file blank line.
