---
name: pr-msg
description: >
  Generate patch/pull-request descriptions for
  cross-service git hosting (GitHub, Gitea,
  SourceHut, GitLab, etc.). Use when user wants
  to create or draft a PR/MR/patch description.
compatibility: >
  Requires git CLI. Optional: gh CLI for PR
  submission.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[base-branch (default: main)]"
disable-model-invocation: true
allowed-tools:
  - Bash(git *)
  - Bash(date *)
  - Bash(cp *)
  - Bash(mkdir *)
  - Read
  - Grep
  - Glob
  - Write
---

When generating a patch-request (PR/MR) description,
always follow this process:

**Narrative flow** — the description should read as
a justification-driven story:

  Motivation (why) → Research (background) →
  Summary (what) → Scopes (where) →
  TODOs before landing (blockers) →
  Follow up (future)

Provide prose only where necessary — typically at
the beginning/end of sections and *around* bullet
segments. Use bullet style wherever there is logical
separation of items that can be tersely expressed as
hierarchical groupings (this is best for piece-wise
technical notes).

0. **Check for branch divergence**: if
   `git log main..HEAD` (or the user-specified base
   branch) is empty, STOP and tell the user "no
   commits diverge from BASE!" with a reminder
   to commit before invoking this skill.

1. **Gather context** from the branch diff and
   commit history:

   - Commit log:
     `git log BASE..HEAD --oneline`
   - Full hashes:
     `git log BASE..HEAD --format='%H %s'`
   - Diffstat:
     `git diff BASE..HEAD --stat`
   - Full diff:
     `git diff BASE..HEAD`
   - Remotes:
     !`git remote -v`
     (to determine commit-link base URL)

2. **Determine the commit-link base URL**:

   Inspect remotes to find the primary hosting
   service and construct the commit URL prefix.
   Preference order:
   - `github` or `origin` remote →
     `https://github.com/<owner>/<repo>/commit/`
   - `gitea` remote → parse the SSH/HTTPS URL
   - `srht` remote →
     `https://git.sr.ht/~<owner>/<repo>/commit/`
   - If multiple remotes exist, default to `github`;
     the user can override via the cross-service
     ref-link stubs.

3. **Analyze the diff**: read through the full diff
   to understand the semantic scope of changes — new
   features, bug fixes, refactors, test coverage,
   etc.

4. **Write the PR description** following these
   rules (includes interactive sub-steps 4a/4b
   that run *before* final text assembly):

   4a. **Suggest related issues/PRs** — see the
       "Related issues & PRs" section below;
       prompt the user with candidates.
   4b. **Suggest reviewers** — see the "Reviewer
       suggestions" section below; prompt the
       user with contributor names.

**Line length: 69 display-columns max** (same as
`set tw=69` in nvim) for ALL prose content —
Motivation paragraphs, Summary bullets, Scopes
bullets, etc. This is a **fill width**: pack each
line as close to 69 columns as possible without
exceeding it (like `gq` in vim). The column count
includes any leading indentation (2-space bullet
continuation, 4-space sub-bullet continuation,
etc.). Same rule as commit-msg body and project
code style. Only raw URLs in reference-link defs
may exceed this.

**Measure rendered width, not raw markdown** — when
a line contains reference-link syntax like
`[display text][ref-id]`, count only the display
text width for wrapping purposes (what a human
reads in rendered output), NOT the full raw syntax.
This means a line with `[`claude-code`][cc-gh]`
counts the display text `` `claude-code` `` (~14
cols), not the full `[`claude-code`][cc-gh]` raw
form (~26 cols).

**Title:**
- Present tense verb (Add, Fix, Drop, Use, etc.)
- Target 50 chars (hard max 70)
- Backticks around ALL code elements
- Specific about what the branch accomplishes

**Use the accompanying style/format reference:**
- See [format-reference.md](format-reference.md)
  for the canonical PR description structure.

**Body Sections (in order):**

Separate major sections with `---` horizontal rules.

### Metadata comment
- Always include an HTML-comment metadata block at
  the very top of the generated file (before the
  title) with branch info and cross-service
  submission placeholders:
  ```
  <!-- pr-msg-meta
  branch: <branch-name>
  base: <base-branch>
  submitted:
    github: ___
    gitea: ___
    srht: ___
  -->
  ```

### Title (h2)
- Use `## <Title>` as the first visible heading.

### Motivation
- 1-2 paragraphs explaining *why* the change exists.
- Describe the problem/limitation before the
  solution.
- **69 char line limit** — hard-wrap paragraphs.
- Casual yet technically precise tone (match the
  project's commit-msg style).
- Comes FIRST — the reader needs to know *why*
  before seeing *what* changed.

### Src of research (optional)
- Include when the change is motivated by external
  specs, RFCs, upstream projects, or design docs.
- Brief intro sentence, then bulleted links.
- Use `*` sub-bullets for specific pages/sections
  within a link group.
- Example:
  ```
  ### Src of research

  The following provide info on why/how this
  impl makes sense,

  - https://github.com/project/repo
    * https://github.com/project/repo/blob/.../file
  - https://datatracker.ietf.org/doc/html/rfc1234
  ```

### Summary of changes
- Use heading `### Summary of changes` (not just
  "Summary").
- Optional subtitle like "By chronological commit"
  when organizing by commit order.
- Bulleted list of changes, one per logical unit.
- Each bullet prefixed with a parenthesized
  commit-hash reference link:
  `([<short-hash>][<short-hash>])` using md
  reference-style.
- End each bullet with a period for prose-y feel.
- Use backticks for all code elements.
- **69 char line limit** — wrap long bullets.
- When a single bullet covers multiple commits,
  chain the hash refs:
  `([abc1234][abc1234]) ([def5678][def5678])`.
- Use `*` sub-bullets for secondary details within
  a change.

### Scopes changed
- **Optional for small PRs** — when the diff is ≤3
  files and "Summary of changes" already covers the
  per-file detail, this section may be omitted to
  reduce noise.
- Organized by file/module path, NOT by commit.
- Use `- \`<scope>\`` prefix with `*` sub-bullets
  for what changed within each scope.
- Use namespace-resolution syntax for scope paths:
  `tractor.discovery._multiaddr` not
  `tractor/discovery/_multiaddr.py`.
- For test modules use `tests.<module_name>` style.
- **69 char line limit** on each bullet line.

### TODOs before landing (optional)
- Include when there are outstanding items that
  should be resolved before the PR merges (missing
  tests, incomplete docs, known edge-case gaps).
- Use a checklist (`- [ ] item`) so reviewers can
  track completion.
- If nothing is blocking, omit entirely.

### Future follow up (optional)
- Include when there are planned next steps, known
  limitations, or follow-up work that builds on
  this PR.
- Actively scan the diff for `# TODO`, `XXX`,
  `FIXME`, and `NOTE` comments — surface any that
  are relevant to follow-up work.
- Use prose paragraphs and/or code examples to
  illustrate the vision.

### Cross-references (commented out)
- Always include a commented-out cross-references
  section as a placeholder for linking the same
  PR/patch across services:
  ```
  <!--
  ### Cross-references
  Also submitted as
  [github-pr][] | [gitea-pr][] | [srht-patch][].

  ### Links
  - [relevant-issue-or-discussion](url)
  - [design-doc-or-screenshot](url)
  -->
  ```

### Related issues & PRs
- Scan commit messages, branch name, and diff for
  issue/PR references (`#123`, `fixes #N`, URLs).
- Search the repo's open issues for keywords from
  the PR title/motivation.
- **Prompt the user**: present any candidate links
  and ask which (if any) to include. Add confirmed
  links to the `### Links` block inside the
  cross-references comment.

### Reviewer suggestions
- Run `git log --format='%aN' -- <changed-files>`
  and `git blame` on heavily modified files to
  identify past contributors.
- **Prompt the user**: suggest tagging those
  collaborators as reviewers, listing each with
  their most-relevant file scope.

### Reference-style link definitions
- Collect ALL commit-hash links at the bottom of
  the document.
- Format:
  `[<short-hash>]: <base-url><full-or-short-hash>`
- Use the 8-char short hash as both display text
  and ref ID.
- This ensures cross-service md compatibility —
  most services will also auto-link bare SHAs but
  the explicit refs are a guaranteed fallback.

### Cross-service PR ref-link stubs
- After the commit-hash refs, include commented-out
  reference-link stubs for each detected remote's
  PR URL pattern, using `___` as the number
  placeholder:
  ```
  <!-- cross-service pr refs (fill after submit):
  [github-pr]: https://github.com/<owner>/<repo>/pull/___
  [gitea-pr]: https://<host>/<owner>/<repo>/pulls/___
  [srht-patch]: https://git.sr.ht/~<owner>/<repo>/patches/___
  -->
  ```
- Only include stubs for remotes actually detected
  via `git remote -v`.

**Footer** (note: the link ref syntax does NOT count
toward the 69-col limit — only the rendered display
text does, so this fits on one line):
```
(this pr content was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

5. **Write to TWO files**:
   - `.claude/skills/pr-msg/msgs/<timestamp>_<branch>_pr_msg.md`
     * `<timestamp>` from `date -u +%Y%m%dT%H%M%SZ`
     * `<branch>` from `git branch --show-current`
   - `.claude/skills/pr-msg/pr_msg_LATEST.md`
     (overwrite)

6. **Present the raw markdown** to the user in a
   fenced code block (` ```` `) so they can
   copy-paste into any git-service web form.

## Post-submission workflow

After the user submits the PR content to one or
more git services, they (or claude via `/gish`)
can:

1. **Fill metadata**: update the `<!-- pr-msg-meta`
   comment's `submitted:` fields with the assigned
   PR/issue numbers.

2. **Uncomment cross-refs**: uncomment the
   `### Cross-references` section and the
   ref-link stubs, filling in actual PR numbers.

3. **Copy to service subdirs**: for each service
   the PR was submitted to, copy the file:
   ```
   msgs/<service>/<pr-num>_pr_msg.md
   ```
   e.g. `msgs/github/42_pr_msg.md`,
   `msgs/gitea/17_pr_msg.md`.

4. **Cross-link**: each service-specific copy gets
   its own PR number filled in AND links to the
   other services' copies. This enables any copy
   to reference the PR on every other service.

This mirrors the `gish` skill's
`<backend>/<num>.md` local-file pattern — see
`modden/.claude/skills/gish/` for the full
cross-service issue/PR management workflow.

**Abbreviations** (same as commit-msg style):
msg, bg, ctx, impl, mod, obvi, tn, fn, bc, var,
prolly, ep, OW, rn, sig, deps, iface, subproc,
tho, ofc

Keep it terse but detailed. Match the project's
casual-technical tone. Every bullet should carry
signal — no filler.
