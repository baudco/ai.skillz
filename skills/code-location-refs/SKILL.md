---
name: code-location-refs
description: >
  Format repository code locations as editor-jumpable Markdown references.
  Use when a response cites source files, definitions, diagnostics, tests, or
  exact line ranges that a human may open from an AI compose buffer.
compatibility: Works with any harness that emits Markdown.
metadata:
  author: goodboy
  version: "0.2"
---

# Code Location References

Make source citations directly navigable without sacrificing readable prose.

## Format

Wrap each location in one inline-code span and use one of these forms:

```text
path/to/file.py:42
path/to/file.py:42-57
path/to/file.py:42:8
```

Use a path relative to the active Git worktree root by default. Establish that
root with `git rev-parse --show-toplevel` and verify that the rendered path
exists beneath it.

When citing a file in another worktree or repository checkout, use its
absolute path:

```text
/absolute/path/to/other-worktree/path/to/file.py:42-57
```

Do not emit a path merely because it was relative to a tool call's temporary
working directory. A relative citation must resolve from the active worktree
root used by the human's editor.

Place sentence punctuation outside the closing backtick. Keep a single
location in each span so cursor-based navigation is unambiguous.

## Accuracy

- Cite only paths and line numbers verified from the current checkout.
- Verify relative citations from the active worktree root, not from an
  incidental command or file-reading directory.
- Use an absolute path when the verified file is outside that active
  worktree, even when it belongs to another worktree of the same repository.
- Use the first substantive line for a single-location citation.
- Use an inclusive range when the explanation depends on a whole section.
- Prefer the narrowest range that supports the claim.
- Refresh line numbers after edits before presenting the final response.
- Do not invent a location when only a symbol name or approximate area is
  known; cite the file alone in prose instead.

## Portability

The colon forms intentionally work as plain text, with Neovim `gF` for paths
without whitespace, and with navigation plugins that add repository-aware
resolution. Backtick-aware navigation is required when a path contains
whitespace. Absolute paths are machine-local but preserve correctness for
cross-worktree citations. Do not substitute web-only `#L42` fragments unless
the user specifically requests forge URLs.
