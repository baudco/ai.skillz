# `ai.skillz`

Reusable AI agent skills for
[`claude-code`](https://github.com/anthropics/claude-code)
conforming to the
[agentskills.io](https://agentskills.io/specification)
specification.

Extracted from real-world Python projects
([`tractor`](https://github.com/goodboy/tractor),
[`piker`](https://github.com/pikers/piker),
[`modden`](https://github.com/goodboy/modden)) and
generalized for cross-repo deployment.

## Skills

| Skill | Description |
|-------|-------------|
| `py-codestyle` | Python code style conventions |
| `commit-msg` | Git commit message generation |
| `pr-msg` | PR description generation |
| `code-review-changes` | Apply PR review feedback |
| `run-tests` | Test runner (template-based) |
| `resolve-conflicts` | Merge conflict resolution |
| `open-wkt` / `close-wkt` | Git worktree lifecycle |
| `plan-io` | Plan file conventions |
| `prompt-io` | AI prompt I/O provenance logging |
| `inter-skill-review` | Cross-skill consistency |
| `gish` | Git-over-SSH transport |
| `yt-url-lookup` | YouTube URL resolution |

## Deployment

Each skill has a `DEPLOY.md` with setup instructions.
Two methods are supported:

- **Symlinks** — absolute links from your repo's
  `.claude/skills/` to this checkout (dev machines)
- **Submodule** — `git submodule add` for portable,
  version-pinned deployment (see `scripts/`)

## License

AGPL-3.0 — see [`LICENSE`](./LICENSE).

Commercial licenses available from
[`baudco`](https://github.com/baudco) for proprietary
use cases. See [`LICENSING.md`](./LICENSING.md) for
details.
