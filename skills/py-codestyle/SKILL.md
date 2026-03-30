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

## Whitespace

- Never write lines containing only whitespace;
  use a bare carriage return (empty line) instead.
