# Issue/PR markdown file format

Local issue/PR files are cached at
`<backend>/<num>.md` (e.g. `gh/414.md`,
`gitea/52.md`) in each repo's root.

## Conventions

These conventions are derived from existing files
across `tractor/gh/` and `piker/gitea/`.

### Structure

- **First line(s)**: summary/description text,
  no `#` heading prefix — just plain prose
  describing the issue or change.
- **`---`**: horizontal rule separators between
  major sections.
- **`### Section Title`**: h3 headers for
  subsections within the body.
- Content uses casual-technical tone matching
  the project's commit style.

### Common sections

```markdown
Summary prose describing the issue or PR
purpose in a few sentences or short paragraph.

---

### Impl deats,

- bullet points describing implementation
- code refs in `backticks`
- nested sub-bullets for detail

---

### Pre-merge todo

- [ ] unchecked item
- [x] completed item

---

### Follow up

- [ ] future work items
- [ ] things to revisit later
```

### Style notes

- Use `backticks` around all code references
  (functions, modules, variables, types).
- Use `- [ ]` / `- [x]` for todo checklists.
- Abbreviations are fine: msg, bg, ctx, impl,
  mod, fn, bc, var, obvi, tn, prolly.
- Section headers often end with `,` per project
  convention (e.g. `### Impl deats,`).
- Casual yet technically precise — match the
  tone of existing issue files and commits.
- Max line length ~67 chars where practical.
- No YAML frontmatter — just plain markdown.
- Links use inline style:
  `[text](https://...)` or bare URLs.

### File naming

- Always `<num>.md` where `<num>` is the issue
  or PR number assigned by the remote service.
- Directory is the backend name: `gh/`, `gitea/`,
  etc.
- Files are created by `gish` xontrib on first
  edit, or manually by claude when drafting.
