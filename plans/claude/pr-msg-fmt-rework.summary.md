Refine `/pr-msg` output to match tractor#429

Add justification-driven narrative flow, interactive
prompts, and new optional sections to the `/pr-msg`
skill so generated PR descriptions match the manually
polished format from tractor PR #429.

- Add "justification driven flow" preamble to
  `SKILL.md` establishing the why→what→where→next
  narrative arc and prose/bullet style guidance.
- Make "Scopes changed" optional for small (≤3 file)
  PRs where "Summary of changes" already covers
  per-file detail.
- Add `### TODOs before landing` section spec using
  `- [ ]` checklists for pre-merge blockers.
- Enhance `### Future follow up` to actively scan
  diffs for `# TODO`, `XXX`, `FIXME`, `NOTE`
  comments.
- Add `### Related issues & PRs` interactive prompt
  — scan commits/branch/diff for references, search
  open issues, prompt user with candidates.
- Add `### Reviewer suggestions` interactive prompt
  — use `git log`/`git blame` on changed files to
  identify past contributors for user to tag.
- Update step 4 with sub-steps 4a/4b for the two
  user prompts before final text assembly.
- Mirror all structural additions in
  `references/format-reference.md` template (TODOs
  section, style principles, updated Links
  placeholder).

Files modified:
- `skills/pr-msg/SKILL.md`
- `skills/pr-msg/references/format-reference.md`

(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
