# PR/Patch-Request Description Format Reference

Canonical structure for `tractor` patch-request
descriptions, designed to work across GitHub,
Gitea, SourceHut, and GitLab markdown renderers.

**Line length: 69 char max** (same as `set tw=69`
in nvim) for all prose content (Summary bullets,
Motivation paragraphs, Scopes bullets, etc.). Same
limit as commit-msg body and project code style.
Only raw URLs in reference-link definitions may
exceed this.

## Template

```markdown
<!-- pr-msg-meta
branch: <branch-name>
base: <base-branch>
submitted:
  github: ___
  gitea: ___
  srht: ___
-->

## <Title: present-tense verb + backticked code>

### Motivation
<1-2 paragraphs: problem/limitation first,
then solution. Hard-wrap at 69 chars.>

---

### Src of research

<optional — include when motivated by external
specs, RFCs, upstream projects, or design docs>

The following provide info on why/how this impl
makes sense,

- https://github.com/project/repo
  * https://github.com/project/repo/blob/.../file
- https://some-rfc-or-spec-url

---

### Summary of changes

By chronological commit

- ([<hash>][<hash>]) Description of change ending
  with period.

- ([<hash>][<hash>]) Another change description
  ending with period.
  * Sub-detail about this change.

- ([<hash>][<hash>]) ([<hash>][<hash>]) Multi-commit
  change description.

---

### Scopes changed
- `pkg.mod`
  * description of what changed.

- `pkg.mod.submod`
  * full rewrite; drop old impl, replace with new.
  * re-export `Thing` from upstream lib.

- `tests.test_mod`
  * add test coverage for new feature.

---

### TODOs before landing

<optional — include when there are pre-merge blockers>

- [ ] Outstanding item one.
- [ ] Outstanding item two.

---

### Future follow up

<optional — planned next steps, known limitations,
or follow-up work. Scan diff for # TODO / XXX /
FIXME / NOTE comments and surface relevant items.>

<!--
### Cross-references
Also submitted as
[github-pr][] | [gitea-pr][] | [srht-patch][].

### Links
- [<repo>#NNN](url) — related issue/PR
- [design-doc-or-screenshot](url)
-->

---

(this pr content was generated in some part by
[`claude-code`][claude-code-gh])

[<hash>]: https://<service>/<owner>/<repo>/commit/<full-hash>
[claude-code-gh]: https://github.com/anthropics/claude-code

<!-- cross-service pr refs (fill after submit):
[github-pr]: https://github.com/<owner>/<repo>/pull/___
[gitea-pr]: https://<host>/<owner>/<repo>/pulls/___
[srht-patch]: https://git.sr.ht/~<owner>/<repo>/patches/___
-->
```

## Markdown Reference-Link Strategy

Use reference-style links for ALL commit hashes
and cross-service PR refs to ensure cross-service
compatibility:

**Inline usage** (in bullets):
```markdown
- [f3726cf9][f3726cf9] Add `reg_err_types()`
  for custom exc lookup.
```

**Definition** (bottom of document):
```markdown
[f3726cf9]: https://github.com/goodboy/tractor/commit/f3726cf9
```

### Why reference-style?
- Keeps prose readable without long inline URLs.
- All URLs in one place — trivially swappable
  per-service.
- Most git services auto-link bare SHAs anyway,
  but explicit refs guarantee it works in *any*
  md renderer.
- The `[hash][hash]` form is self-documenting —
  display text matches the ref ID.
- Cross-service PR refs use the same mechanism:
  `[github-pr][]` resolves via a ref-link def
  at the bottom, trivially fillable post-submit.

## Cross-Service PR Placeholder Mechanism

The generated description includes three layers
of cross-service support, all using native md
reference-links:

### 1. Metadata comment (top of file)

```markdown
<!-- pr-msg-meta
branch: remote_exc_type_registry
base: main
submitted:
  github: ___
  gitea: ___
  srht: ___
-->
```

A YAML-ish HTML comment block. The `___`
placeholders get filled with PR/patch numbers
after submission. Machine-parseable for tooling
(e.g. `gish`) but invisible in rendered md.

### 2. Cross-references section (in body)

```markdown
<!--
### Cross-references
Also submitted as
[github-pr][] | [gitea-pr][] | [srht-patch][].
-->
```

Commented out at generation time. After submitting
to multiple services, uncomment and the ref-links
resolve via the stubs at the bottom.

### 3. Ref-link stubs (bottom of file)

```markdown
<!-- cross-service pr refs (fill after submit):
[github-pr]: https://github.com/goodboy/tractor/pull/___
[gitea-pr]: https://pikers.dev/goodboy/tractor/pulls/___
[srht-patch]: https://git.sr.ht/~goodboy/tractor/patches/___
-->
```

Commented out with `___` number placeholders.
After submission: uncomment, replace `___` with
the actual number. Each service-specific copy
fills in all services' numbers so any copy can
cross-reference the others.

### Post-submission file layout

```
msgs/
  pr_msg_LATEST.md                  # latest draft
  20260325T002027Z_mybranch_pr_msg.md  # timestamped
  github/
    42_pr_msg.md        # github PR #42
  gitea/
    17_pr_msg.md        # gitea PR #17
  srht/
    5_pr_msg.md         # srht patch #5
```

Each `<service>/<num>_pr_msg.md` is a copy with:
- metadata `submitted:` fields filled in
- cross-references section uncommented
- ref-link stubs uncommented with real numbers
- all services cross-linked in each copy

This mirrors the `gish` skill's
`<backend>/<num>.md` pattern.

## Commit-Link URL Patterns by Service

| Service   | Pattern                             |
|-----------|-------------------------------------|
| GitHub    | `https://github.com/<o>/<r>/commit/<h>` |
| Gitea     | `https://<host>/<o>/<r>/commit/<h>` |
| SourceHut | `https://git.sr.ht/~<o>/<r>/commit/<h>` |
| GitLab    | `https://gitlab.com/<o>/<r>/-/commit/<h>` |

## PR/Patch URL Patterns by Service

| Service   | Pattern                             |
|-----------|-------------------------------------|
| GitHub    | `https://github.com/<o>/<r>/pull/<n>` |
| Gitea     | `https://<host>/<o>/<r>/pulls/<n>`  |
| SourceHut | `https://git.sr.ht/~<o>/<r>/patches/<n>` |
| GitLab    | `https://gitlab.com/<o>/<r>/-/merge_requests/<n>` |

## Scope Naming Convention

Use Python namespace-resolution syntax for
referencing changed code scopes. Organize by
file/module path, NOT by commit.

| File path                 | Scope reference               |
|---------------------------|-------------------------------|
| `tractor/_exceptions.py`  | `tractor._exceptions`         |
| `tractor/_state.py`       | `tractor._state`              |
| `pyproject.toml`          | `pyproject.toml`              |
| `tests/test_foo.py`       | `tests.test_foo`              |
| Function in module        | `tractor._exceptions.func()`  |
| Method on class           | `.RemoteActorError.src_type`  |
| Class                     | `tractor._exceptions.RAE`     |

Each scope gets a top-level `-` bullet with the
backticked path, then `*` sub-bullets describing
what changed within that scope:

```markdown
- `tractor.discovery._multiaddr`
  * full rewrite; drop `bidict`-based protocol
    tables, custom parser fns.
  * re-export `Multiaddr` from upstream lib.

- `tractor.ipc._tcp`
  * `.maddr` now returns `Multiaddr` via
    `mk_maddr(self.raddr)`, auto-detects ip4/ip6.
```

Prefix with the package path for top-level refs;
use leading-dot shorthand (`.ClassName.method()`)
for sub-bullets where the parent module is already
established.

## Title Conventions

Same verb vocabulary as commit messages:
- `Add` — wholly new feature/API
- `Fix` — bug fix
- `Drop` — removal
- `Use` — adopt new approach
- `Move`/`Mv` — relocate code
- `Adjust` — minor tweak
- `Update` — enhance existing feature
- `Support` — add support for something

Target 50 chars, hard max 70. Always backtick
code elements.

## Tone

Casual yet technically precise — matching the
project's commit-msg style. Terse but every bullet
carries signal. Use project abbreviations freely
(msg, bg, ctx, impl, mod, obvi, fn, bc, var,
prolly, ep, etc.).

## Style principles

- **Justification-driven flow** — sections progress
  from *why* → *what* → *where* → *next*.
- Prose only at section openings/closings and around
  bullet segments.
- Bullets for any logical separation expressible as
  terse hierarchical groupings.
- Every bullet carries signal — no filler.

---

(this format reference was generated by
[`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
