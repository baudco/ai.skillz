---
name: code-location-refs
description: >
  Format repository code locations as editor-jumpable Markdown references.
  Use when a response cites source files, definitions, diagnostics, tests, or
  exact line ranges that a human may open from an AI compose buffer.
compatibility: Works with any harness that emits Markdown.
metadata:
  author: goodboy
  version: "0.1"
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

Use a repository-relative path by default. When citing another repository,
prefix the path with that repository's checkout basename:

```text
other-repo/path/to/file.py:42-57
```

Place sentence punctuation outside the closing backtick. Keep a single
location in each span so cursor-based navigation is unambiguous.

## Accuracy

- Cite only paths and line numbers verified from the current checkout.
- Use the first substantive line for a single-location citation.
- Use an inclusive range when the explanation depends on a whole section.
- Prefer the narrowest range that supports the claim.
- Refresh line numbers after edits before presenting the final response.
- Do not invent a location when only a symbol name or approximate area is
  known; cite the file alone in prose instead.

## Portability

The colon forms intentionally work as plain text, with Neovim `gF`, and with
navigation plugins that add repository-aware resolution. Do not substitute
web-only `#L42` fragments unless the user specifically requests forge URLs.
