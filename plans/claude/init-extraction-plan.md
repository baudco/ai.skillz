# Plan: Extract and generalize AI skills into `ai.skillz`

## Context

Skills (`.claude/skills/`) are scattered across 4 repos
(`dotrc`, `tractor`, `piker`, `modden`) with inconsistent
inheritance via symlinks. This plan factors out everything
**not repo-specific** into a new canonical `ai.skillz` repo,
conforming to the [agentskills.io](https://agentskills.io/specification)
spec and designed for cross-provider compatibility.

---

## Phase 0: Git repo init + history extraction

Use `git-filter-repo` to extract `.claude/skills/` commit
histories from each source repo, then merge into `ai.skillz`.

### Steps

1. `git init` in `/home/goodboy/repos/ai.skillz/`
2. Create initial commit with existing `prompts/init.md`
   and `.claude/settings.local.json`
3. For each source repo, clone to `/tmp/`, filter, merge:

**dotrc** (13 commits, most global skills):
```
git clone ~/repos/dotrc /tmp/dotrc-filtered
cd /tmp/dotrc-filtered
git filter-repo \
  --path dotrc/claude/skills/ \
  --path-rename 'dotrc/claude/skills/:skills/'
```

**tractor** (pr-msg, commit-msg style guide, run-tests template):
```
git clone ~/repos/tractor /tmp/tractor-filtered
cd /tmp/tractor-filtered
git filter-repo \
  --path .claude/skills/commit-msg/style-guide-reference.md \
  --path .claude/skills/pr-msg__checkout/ \
  --path .claude/skills/pr-msg/ \
  --path .claude/skills/run-tests/SKILL.md \
  --path-rename '.claude/skills/:skills/'
```

**piker** (commit-msg style guide only):
```
git clone ~/repos/piker /tmp/piker-filtered
cd /tmp/piker-filtered
git filter-repo \
  --path .claude/skills/commit-msg/style-guide-reference.md \
  --path-rename '.claude/skills/:skills/'
```

**modden** (gish + modden style guide):
```
git clone ~/repos/modden /tmp/modden-filtered
cd /tmp/modden-filtered
git filter-repo \
  --path .claude/skills/gish/ \
  --path .claude/skills/commit-msg/style-guide-reference.md \
  --path-rename '.claude/skills/:skills/'
```

4. Merge each filtered repo:
```
git remote add <name>-import /tmp/<name>-filtered
git fetch <name>-import
git merge --allow-unrelated-histories <name>-import/<branch>
```
   - Resolve conflicts: keep dotrc's version of shared files,
     move repo-specific variants to `references/examples/`
5. Clean up remotes + `/tmp/` clones

### Conflict resolution priority
- `commit-msg/SKILL.md`: dotrc version wins (most evolved)
- `style-guide-reference.md`: each gets renamed to
  `references/<repo>-style-guide.md` under `commit-msg/`

---

## Phase 1: Directory layout + agentskills.io compliance

### Target structure

```
ai.skillz/
├── skills/
│   ├── commit-msg/
│   │   ├── SKILL.md              # generic workflow (from dotrc)
│   │   ├── DEPLOY.md
│   │   ├── ROADMAP.md
│   │   └── references/
│   │       ├── tractor-style-guide.md
│   │       ├── piker-style-guide.md
│   │       └── modden-style-guide.md
│   ├── pr-msg/
│   │   ├── SKILL.md              # from tractor pr-msg__checkout
│   │   ├── DEPLOY.md
│   │   ├── ROADMAP.md
│   │   └── references/
│   │       └── format-reference.md
│   ├── code-review-changes/
│   │   ├── SKILL.md
│   │   ├── DEPLOY.md
│   │   └── ROADMAP.md
│   ├── inter-skill-review/
│   │   ├── SKILL.md
│   │   └── DEPLOY.md
│   ├── resolve-conflicts/
│   │   ├── SKILL.md
│   │   └── DEPLOY.md
│   ├── py-codestyle/
│   │   ├── SKILL.md
│   │   └── DEPLOY.md
│   ├── yt-url-lookup/
│   │   ├── SKILL.md
│   │   ├── DEPLOY.md
│   │   └── ROADMAP.md
│   ├── gish/
│   │   ├── SKILL.md
│   │   ├── DEPLOY.md
│   │   ├── ROADMAP.md
│   │   └── references/
│   │       ├── backends.md
│   │       └── format.md
│   └── run-tests/
│       ├── DEPLOY.md             # template-only, not a live skill
│       └── references/
│           └── tractor-example.md
├── templates/
│   ├── commit-msg/
│   │   ├── style-guide-reference.md.j2
│   │   └── conf.toml.j2
│   ├── pr-msg/
│   │   └── format-reference.md.j2
│   └── run-tests/
│       └── SKILL.md.j2
├── scripts/
│   ├── deploy-skill.sh
│   ├── generate-style-guide.py
│   └── validate-skills.sh
├── prompts/
│   └── init.md
├── .claude/
│   └── settings.local.json
├── CLAUDE.md
└── README.md
```

### agentskills.io compliance changes

Add YAML frontmatter to every `SKILL.md`:
```yaml
---
name: <dir-name>
description: <what it does + when to use it>
compatibility: Designed for Claude Code (or similar
  agentic coding tools with tool-use capabilities)
metadata:
  author: goodboy
  version: "0.1"
allowed-tools: <existing tool lists, kept as-is>
---
```

All current skill directory names already comply with
the `name` field spec (lowercase + hyphens).

`pr-msg__checkout/` gets renamed to `pr-msg/` (double
underscores violate the spec).

---

## Phase 2: Skill refactoring

### 2a: `commit-msg`
- Use dotrc's 279-line SKILL.md as canonical (most evolved:
  session tracking, worktree detection, regression context,
  review PATCH flow)
- Move 3 repo-specific style guides into `references/`
- Keep conditional style-guide discovery logic (already in
  dotrc version at step 2)

### 2b: `pr-msg`
- Use tractor's `pr-msg__checkout/SKILL.md` (231 lines) —
  the only complete version
- Move `format-reference.md` (242 lines) to `references/`
- Generalize tractor-specific scope naming examples

### 2c: `code-review-changes`
- Already fully generic in dotrc (340 lines)
- Add ROADMAP.md noting `gh api` → `gish` migration path
- Note `/run-tests` cross-reference is optional

### 2d: `gish`
- Move wholesale from modden
- `backends.md`, `format.md` → `references/`
- `roadmap.md` → `ROADMAP.md`
- Update canonical-source reference from modden to ai.skillz

### 2e: `yt-url-lookup`
- At 499 lines, near the 500-line spec limit
- Extract inline Python to `scripts/` if feasible
- Merge existing `ROADMAP.md` (media skills family)

### 2f: Simple migrations (minimal changes)
- `py-codestyle` (134 lines) — add frontmatter
- `resolve-conflicts` (138 lines) — add frontmatter
- `inter-skill-review` (220 lines) — add frontmatter

### 2g: `run-tests` (template only)
- Tractor's SKILL.md becomes `references/tractor-example.md`
- Create Jinja2 template with placeholders for project-
  specific sections (test dir, import check, known flaky, etc.)

---

## Phase 3: Templates + deployment docs

### 3a: Jinja2 templates

**`templates/commit-msg/style-guide-reference.md.j2`**
Common structure extracted from tractor/piker/modden guides:
- `{{ repo_name }}`, `{{ commits_analyzed }}`
- `{{ verb_frequencies }}` — table of opening verbs
- `{{ backtick_terms }}` — project-specific code elements
- `{{ abbreviations }}` — project-specific shorthand
- `{{ colon_usage_pct }}` — module-prefix colon style
- `{{ domain_terms }}`, `{{ tone_notes }}`

**`templates/run-tests/SKILL.md.j2`**
Placeholders: `{{ project_name }}`, `{{ test_runner }}`,
`{{ test_dir }}`, `{{ import_check }}`, `{{ test_layout }}`,
`{{ change_test_mapping }}`, `{{ known_flaky }}`,
`{{ custom_flags }}`

**`templates/commit-msg/conf.toml.j2`**
Minimal session tracking boilerplate.

### 3b: `scripts/generate-style-guide.py`
Python script that:
1. Runs `git log` analysis (last N commits)
2. Extracts verb frequencies, backtick usage, abbreviations
3. Renders `style-guide-reference.md.j2` with results
4. Outputs to target path

### 3c: `scripts/deploy-skill.sh`
Shell script:
1. Takes skill name + target repo path
2. Creates `.claude/skills/<name>/` in target
3. Symlinks generic SKILL.md from ai.skillz
4. Copies/renders templates for per-repo files
5. Creates `msgs/` dir if needed

### 3d: Per-skill `DEPLOY.md`
Each skill gets a `DEPLOY.md` explaining:
- Prerequisites (tools, env)
- Quick setup (symlink + local overrides)
- What files stay local vs. symlinked
- How to customize

---

## Phase 4: Roadmaps + gish integration notes

### Per-skill ROADMAPs

| Skill | Key future items |
|-------|-----------------|
| `commit-msg` | `gish` transport for PATCH flow, auto style-guide gen |
| `pr-msg` | `gish pr create` replacing `gh pr create`, cross-service |
| `code-review-changes` | `gish review`/`gish reply` replacing `gh api` |
| `gish` | Full 6-phase roadmap from modden (909 lines) |
| `yt-url-lookup` | media skills family (yt-dl-audio, audio-quality-check, beet-import) |

### Architecture vision (from gish roadmap)
```
AI skills (content layer)
  ↓ writes local md files
gish (transport layer)
  ↓ backend-specific sync
Backends (GitHub, Gitea, sr.ht, GitLab, plain git)
```

All skills currently using `gh api` get a roadmap note about
migrating to `gish` as the transport abstraction.

---

## Phase 5: Cross-provider compatibility pass

- Keep Claude-Code-specific fields (`allowed-tools`,
  `disable-model-invocation`, `argument-hint`) — they're
  harmless for other providers (just ignored)
- Add `compatibility` field to each SKILL.md per spec
- In instruction bodies, describe operations generically
  where possible ("read the file" vs "use the Read tool")
- Keep tool-name references in `allowed-tools` (Claude-specific)

---

## Deferred: Symlink restructure

After `ai.skillz` is validated and working, a follow-up
session will update symlinks in all repos to point here
instead of through dotrc:
```
~/.claude/skills/ → ai.skillz/skills/
tractor: SKILL.md symlinks → ai.skillz
piker: SKILL.md symlinks → ai.skillz
modden: gish symlink direction flips → ai.skillz
```

---

## Verification

1. `git log --oneline` shows merged histories from all 4 repos
2. Every `skills/*/SKILL.md` has valid YAML frontmatter
   (`name` matches dir, `description` present)
3. No repo-specific content in generic SKILL.md files
4. Templates render correctly:
   `python scripts/generate-style-guide.py --repo ~/repos/tractor`
5. `deploy-skill.sh` creates correct symlink structure
6. Existing repos still work via current symlinks (deferred
   migration means no disruption)
