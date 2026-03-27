Extract and generalize AI skills into `ai.skillz`

- Extract `.claude/skills/` commit histories from `dotrc`,
  `tractor`, `piker`, `modden` via `git-filter-repo` and
  merge into new canonical repo with `--allow-unrelated-histories`
- Factor 9 skills: `commit-msg`, `code-review-changes`,
  `pr-msg`, `inter-skill-review`, `resolve-conflicts`,
  `py-codestyle`, `yt-url-lookup`, `gish`, `run-tests`
  (template-only)
- Add YAML frontmatter (`name`, `description`,
  `compatibility`, `metadata`) per agentskills.io spec
  to all 8 live SKILL.md files (0 validation errors)
- Restructure `gish/` references and update canonical
  source from `modden` to `ai.skillz`
- Bring in previously untracked `/pr-msg` from tractor
  (rename `pr-msg__checkout` dir for spec compliance)
- Move 3 repo-specific `style-guide-reference.md` files
  to `skills/commit-msg/references/<repo>-style-guide.md`
- Create Jinja2 templates for commit-msg style guide,
  `conf.toml`, and run-tests SKILL.md under `templates/`
- Write `DEPLOY.md` for all 9 skills with symlink setup,
  per-repo customization, and prerequisites
- Write `ROADMAP.md` for `commit-msg`, `pr-msg`,
  `code-review-changes` documenting `gish` migration path
- Create `scripts/deploy-skill.sh` and
  `scripts/validate-skills.sh`

## Completed (post-plan)

- Global `~/.claude/skills/` symlink repointed from
  `dotrc/dotrc/claude/skills/` to `ai.skillz/skills/`
- `/plan-io` skill created for plan file I/O conventions

## Deferred

- Per-repo symlink migration (tractor, piker, modden)
- `scripts/generate-style-guide.py` (needs `jinja2`)
- `flake.nix` (user-managed)

## Stats

- 41 commits (merged from 4 repos + new work)
- 35 files across `skills/`, `templates/`, `scripts/`
- 0 validation errors, 1 warning (`yt-url-lookup` 505 lines)

(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
