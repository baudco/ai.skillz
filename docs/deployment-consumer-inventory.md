# Deployment consumer inventory

This is a read-only snapshot of known `ai.skillz` consumers observed on
2026-07-23. No deployment, migration, configuration edit, staging, or
other mutation was performed in any consumer repository.

The observations below predate the integrated `run-tests` hybrid skill and
OpenCode `run-tests` / `taken-export` command manifest entries. Statements
that those assets were template-only or unsupported describe the audited
consumer state at that time, not the current deployment manifest.

The audit inspected each repository's current worktree and branch, Git
status, `.ai/ai.skillz` and legacy `.claude/ai.skillz` anchors, provider
skill and command trees, standard OpenCode config paths, absolute links,
and `commit-msg` / `pr-msg` hybrid state. It also ran the new
`deploy.sh status <repo> --provider all` read-only inspection.

All six observed worktrees were dirty. The commands below are
recommendations only: re-run `git status`, preserve unrelated staged and
unstaged changes, and review every `migrate --dry-run` result before any
mutation. Run them only after this deployment implementation is
available in `/home/goodboy/repos/ai.skillz`.

## Status terms

| Result | Meaning |
|--------|---------|
| `migrated` | Healthy `.ai/ai.skillz` anchor with relative provider links. |
| `direct Phase-0` | Local absolute provider links exist without the provider-neutral anchor. |
| `not deployed` | No usable canonical skill or command deployment was found. |
| `blocked/manual follow-up` | Existing project-owned, stale, or unsupported assets prevent a fully automatic migration. |

No audited consumer currently qualifies as `migrated`.

## Summary

| Consumer | Observed worktree / branch | Result |
|----------|----------------------------|--------|
| `lns` | `/home/goodboy/repos/lns` / `lns_n_taken_supervisor` | `direct Phase-0` |
| `tractor` | `/home/goodboy/repos/tractor` / `boot_latency_470` | `direct Phase-0` |
| `piker` | `/home/goodboy/repos/piker` / `flake_update` | `blocked/manual follow-up` |
| `modden` | `/home/goodboy/repos/modden` / `trowsers_wks_integrate` | `blocked/manual follow-up` |
| `ai.reply` | `/home/goodboy/repos/ai.reply` / `main` | `not deployed` |
| `ai.skillz` | `/home/goodboy/repos/ai.skillz` / `taken_export_skill`; implementation worktree `wkt/portable_cross_provider_deploy` | `blocked/manual follow-up` |

## `lns`

**Observed state:** `direct Phase-0`.

- Worktree: `/home/goodboy/repos/lns`, branch
  `lns_n_taken_supervisor`, ahead of its configured upstream by 18.
- Dirty-state caveat: tracked staged and unstaged changes plus untracked
  `.claude/`, `claude_wkts`, and other files were present. In particular,
  `taken/current.org` was already staged and must remain untouched.
- Anchors: neither `.ai/ai.skillz` nor `.claude/ai.skillz` exists.
- Claude skills: hybrid `.claude/skills/commit-msg/` with an ignored
  absolute `SKILL.md` link to the `ai.skillz` checkout.
- OpenCode skills: hybrid `.opencode/skills/commit-msg/` with the same
  ignored absolute source link.
- Commands: tracked regular `.opencode/commands/commit-msg.md`; no
  Claude command from the deployment manifest.
- OpenCode config: tracked `.opencode/opencode.json`; it has no
  `skills.paths` entry. Its `~/...` values are permission paths, not an
  absolute skill-catalog deployment.
- Hybrid local state: `.claude/skills/commit-msg/conf.toml` and `msgs/`
  are present and untracked/ignored. Migration must preserve them.
- Status result at audit time: the provider links were recognized as
  local-only absolute links and the tracked command matched the then-current
  canonical copy. The current manifest deploys that command as an ignored
  local link, so the tracked copy must be deliberately untracked first.

Recommended local-anchor migration, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/lns
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO" --dry-run
# After reviewing the dry run and dirty worktree:
# This stages only the intentional removal of the old tracked command copy.
git -C "$REPO" rm --cached -- .opencode/commands/commit-msg.md
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO"
bash "$SKILLZ/scripts/deploy.sh" commit-msg "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" command commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

## `tractor`

**Observed state:** `direct Phase-0`.

- Worktree: `/home/goodboy/repos/tractor`, branch `boot_latency_470`.
- Dirty-state caveat: tracked edits and multiple untracked analysis,
  prompt-log, and documentation paths were present.
- Anchors: neither current nor legacy anchor exists.
- Claude skills: absolute, ignored links for `close-wkt`,
  `code-review-changes`, `inter-skill-review`, `open-wkt`, `plan-io`,
  `prompt-io`, `py-codestyle`, `resolve-conflicts`, and `taken-export`;
  hybrid absolute links for `commit-msg` and `pr-msg`; tracked local
  `run-tests` and `conc-anal` directories.
- OpenCode skills: an absolute, ignored `taken-export` link.
- Commands: no command was recognized by the manifest at audit time. The
  untracked OpenCode `taken-export` command link now has a canonical manifest
  entry and can be replaced after reviewing its source.
- OpenCode config: no standard project `opencode.json` or
  `opencode.jsonc` was found.
- Hybrid local state: tracked `commit-msg/style-guide-reference.md`;
  local `commit-msg/conf.toml` and `msgs/`; local `pr-msg/msgs/` and
  `pr_msg_LATEST.md`. The generated `run-tests/SKILL.md` is local and
  status reports it healthy.
- Status result: all recognized canonical links are healthy Phase-0
  links. Missing manifest commands are informational.

Recommended local-anchor migration, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/tractor
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO" --dry-run
# First extract the tracked run-tests SKILL.md project guidance into
# .claude/skills/run-tests/test-harness-reference.md, then deliberately
# remove the old tracked SKILL.md. After reviewing those changes:
git -C "$REPO" rm -- .claude/skills/run-tests/SKILL.md
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO"
bash "$SKILLZ/scripts/deploy.sh" run-tests "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" command run-tests "$REPO" --provider opencode
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

Review the existing `.opencode/commands/taken-export.md`, then refresh it
through `deploy.sh command taken-export ... --provider opencode` once its
matching skill is healthy.

## `piker`

**Observed state:** `blocked/manual follow-up` with Phase-0 components.

- Worktree: `/home/goodboy/repos/piker`, branch `flake_update`, ahead of
  its configured upstream by 5.
- Dirty-state caveat: `.gitignore` was modified and multiple paths were
  untracked, including the absolute `py-codestyle` link.
- Anchors: neither current nor legacy anchor exists.
- Claude skills: tracked project-local `commit-msg` and domain skills;
  untracked absolute `py-codestyle` link.
- OpenCode skills: ignored absolute hybrid `commit-msg/SKILL.md` link.
- Commands: tracked regular `.opencode/commands/commit-msg.md`; no
  Claude manifest command.
- OpenCode config: no standard project config was found.
- Hybrid local state: tracked Claude `commit-msg/SKILL.md` and
  `style-guide-reference.md`, with local `conf.toml` and `msgs/`.
- Status result: unhealthy because the tracked Claude `SKILL.md` is a
  regular project-owned file, the absolute `py-codestyle` link is not
  ignored, and the OpenCode command copy differs from the canonical
  provider asset. The deploy script intentionally refuses to overwrite
  the project-owned Claude file.

Recommended inspection and post-decision commands, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/piker
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO" --dry-run
# First decide whether the tracked Claude commit-msg SKILL.md remains
# project-owned or is replaced by the canonical hybrid link.
# Also decide whether the tracked OpenCode command is replaced by the
# canonical shim; if so, remove that tracked file before deployment.
# When canonical ownership is selected for both:
git -C "$REPO" rm -- .claude/skills/commit-msg/SKILL.md
git -C "$REPO" rm -- .opencode/commands/commit-msg.md
# After those reviewed manual decisions:
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO"
bash "$SKILLZ/scripts/deploy.sh" commit-msg "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" command commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

## `modden`

**Observed state:** `blocked/manual follow-up` with Phase-0 components.

- Worktree: `/home/goodboy/repos/modden`, branch
  `trowsers_wks_integrate`, ahead of its configured upstream by 55.
- Dirty-state caveat: `.gitignore` was modified and several untracked
  prompt, Nix, and notes paths were present.
- Anchors: neither current nor legacy anchor exists.
- Claude skills: absolute links for `code-review-changes`,
  `inter-skill-review`, `py-codestyle`, and `taken-export`; canonical
  hybrid absolute links for `commit-msg` and `pr-msg`; tracked local
  `gish` and `modden-layout-engine`; `run-tests` links to tractor's local
  generated skill rather than a modden-owned generated file.
- OpenCode skills: absolute `commit-msg` and `taken-export` links plus a
  tracked relative link from `modden-layout-engine` to its Claude skill.
- Commands at audit time: untracked absolute `commit-msg` and then-unsupported
  `taken-export` OpenCode command links. Both now have manifest operations.
  The legacy Claude
  `.claude/commands/branch-in-term.md` link is broken and does not match
  the manifest's `branch-in-new-terminal` name.
- OpenCode config: no standard project config was found.
- Hybrid local state: tracked `commit-msg/style-guide-reference.md`;
  local commit configuration/messages; local `pr-msg/msgs/` and latest
  draft. These must survive any source relinking.
- Status result: unhealthy because tracked `gish` is project-local,
  `run-tests` points to another consumer's skill, the OpenCode command copy
  differs from the provider asset, and legacy commands need manual
  disposition.

Recommended inspection and post-decision commands, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/modden
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO" --dry-run
# First reconcile project-owned gish, extract Modden test guidance into
# test-harness-reference.md, manually unlink the Tractor-owned run-tests
# directory link, and review legacy command links.
test -L "$REPO/.claude/skills/run-tests"
rm "$REPO/.claude/skills/run-tests"
# After those reviewed manual decisions:
bash "$SKILLZ/scripts/deploy.sh" migrate "$REPO"
bash "$SKILLZ/scripts/deploy.sh" commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/deploy.sh" command commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/deploy.sh" run-tests "$REPO" --provider all
bash "$SKILLZ/scripts/deploy.sh" command run-tests "$REPO" --provider opencode
bash "$SKILLZ/scripts/deploy.sh" command taken-export "$REPO" --provider opencode
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

## `ai.reply`

**Observed state:** `not deployed`.

- Worktree: `/home/goodboy/repos/ai.reply`, branch `main`.
- Dirty-state caveat: `.claude/`, `Session.vim`, and `gh/` were
  untracked.
- Anchors: neither current nor legacy anchor exists.
- Claude skills: `.claude/skills/commit-msg/` exists only as local
  state; it has no `SKILL.md`.
- OpenCode skills and commands: none found.
- OpenCode config: no standard project config was found.
- Hybrid local state: untracked `commit-msg/conf.toml` and `msgs/` must
  be preserved if the skill is deployed.
- Status result: unhealthy missing Claude `commit-msg/SKILL.md` and no
  enabled OpenCode provider tree.

Recommended local deployment, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/ai.reply
bash "$SKILLZ/scripts/deploy.sh" init "$REPO" --method symlink
bash "$SKILLZ/scripts/deploy.sh" commit-msg "$REPO" --provider claude
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

## `ai.skillz`

**Observed state:** `blocked/manual follow-up` for source-repository
self-hosting.

- Main worktree: `/home/goodboy/repos/ai.skillz`, branch
  `taken_export_skill`, ahead of its configured upstream by 1.
- Implementation worktree:
  `/home/goodboy/repos/ai.skillz/.claude/wkts/portable_cross_provider_deploy`,
  branch `wkt/portable_cross_provider_deploy`.
- Dirty-state caveat: both worktrees were dirty. The implementation
  worktree contains this deployment work and concurrent script/test
  changes; the main worktree contains unrelated tracked and untracked
  changes.
- Anchors: neither current nor legacy anchor exists in the main
  worktree. The source repository intentionally loads its own canonical
  tree rather than consuming itself through a submodule.
- Claude skills: local hybrid `commit-msg` with an absolute self-link
  and local state; `pr-msg` has local messages/latest state but no
  canonical source assets.
- OpenCode skills: no `.opencode/skills/` links in the main worktree.
  Tracked `opencode.json` uses portable relative `skills.paths:
  ["skills"]`, so this source checkout exposes its canonical skills
  without an absolute config entry.
- Commands: the main worktree has a tracked regular OpenCode
  `commit-msg` shim. This implementation worktree converts that path to
  the tracked relative link
  `../../providers/opencode/commands/commit-msg.md`.
- Hybrid local state: local `commit-msg/conf.toml` and `msgs/`, plus
  local `pr-msg/msgs/` and `pr_msg_LATEST.md`.
- Status result: when inspected from the not-yet-updated main worktree,
  the OpenCode command is content-healthy but its dependency is not
  recognized through this implementation worktree's source root;
  incomplete Claude `pr-msg` assets are also unhealthy. Re-evaluate
  self-host status after this branch lands.

Recommended self-host follow-up after merge, not yet performed:

```bash
SKILLZ=/home/goodboy/repos/ai.skillz
REPO=/home/goodboy/repos/ai.skillz
bash "$SKILLZ/scripts/deploy.sh" status "$REPO" --provider all
# Populate missing canonical pr-msg assets without replacing local state.
bash "$SKILLZ/scripts/deploy.sh" pr-msg "$REPO" \
  --provider claude --method symlink --direct
bash "$SKILLZ/scripts/deploy.sh" commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/deploy.sh" command commit-msg "$REPO" --provider opencode
bash "$SKILLZ/scripts/validate-deployment.sh" "$REPO"
```

Do not add an absolute OpenCode `skills.paths`: the existing relative
`skills` entry is the intended self-hosted source-repository exception.
