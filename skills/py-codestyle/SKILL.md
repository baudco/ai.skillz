---
name: py-codestyle
description: >
  Python coding style conventions. Auto-applied when
  writing or editing Python code.
compatibility: >
  Language-agnostic agent. No external tools needed.
metadata:
  author: goodboy
  version: "0.1"
disable-model-invocation: true
---

# Python code style guide

These rules apply globally to ALL python projects.

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

      Extended description if needed following
      standard PEP guidelines.

      '''
  ```

  Rules:
  * first line contains ONLY `'''` + newline
  * content follows std PEP guidelines
  * final 2 lines: a blank line, then closing `'''`

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

- In any branch condition (`if`/`elif`/`while`/`assert`)
  that combines sub-expressions with boolean
  connectives (`and`/`or`), put each **connective on
  its OWN line**, separate from the operand
  expressions it joins. The operands each get their
  own line(s) too. This keeps every clause visually
  isolated and makes diffs that add/remove a clause
  minimal — same spirit as the multi-line tuple rules.
- Apply this whenever the condition has more than one
  operand, even if it would fit on one line. A single
  operand (`if ready:`, `while not done:`) stays
  inline.

  ```python
  # GOOD - each operand + connective on its own line
  if (
      grandrent is con.workspace()
      or
      any('wks' in mrk for mrk in grandrent.marks)
  ):
      ...

  if (
      rescued
      and
      (cur_src_id := src_node.id) in con_ids
  ):
      ...

  # BAD - connective jammed inline with operands
  if rescued and (cur_src_id := src_node.id) in con_ids:
      ...

  # BAD - connective trailing an operand line
  if (
      grandrent is con.workspace() or
      any('wks' in mrk for mrk in grandrent.marks)
  ):
      ...
  ```

- The same shape applies to a boolean assigned to a
  named local (`reset_ppt: bool = (...)`) — operands
  and connectives each on their own line.

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
