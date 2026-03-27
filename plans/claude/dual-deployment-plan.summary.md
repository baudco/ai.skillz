Add dual deployment: submodule + symlink support

- Add root `.gitignore` with standard ignores
  (`__pycache__/`, `*.pyc`, `py313/`, `Session.vim`, `*.swp`)
- Rewrite `scripts/deploy-skill.sh` with subcommand CLI:
  - `init <repo>` — add `ai.skillz` as git submodule at
    `.claude/ai.skillz/` with optional `--url`/`--ref`
  - `<skill> <repo>` — deploy single skill, auto-detect
    symlink vs submodule method (`--method` override)
  - `update <repo>` — update submodule to latest or `--ref`
  - `status <repo>` — show deployed skills, link types
    (absolute/relative/hybrid/local), broken link detection
- Submodule mode create relative symlinks:
  - dir-links: `../ai.skillz/skills/<name>`
  - hybrid file-links: `../../ai.skillz/skills/<name>/SKILL.md`
- Update all 10 `skills/*/DEPLOY.md` with dual instructions:
  - Method A — absolute symlinks (single-machine)
  - Method B — git submodule (portable, version-pinned)
  - `run-tests` notes neither method apply (template-only)
- Validation: `validate-skills.sh` pass (0 errors),
  `bash -n` syntax check pass, `status` subcommand
  verify against `ai.skillz` and `tractor`

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
