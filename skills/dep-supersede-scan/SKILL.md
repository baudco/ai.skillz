---
name: dep-supersede-scan
description: >
  Scan the current branch's dependency bumps against
  open dependabot alerts + bot-authored PRs, then flag
  any the branch *already satisfies* but hasn't linked,
  superseded, or closed. Output feeds straight into
  `/pr-msg`'s "Related issues & PRs" / Links pass. Use
  when drafting/refreshing a PR that touches dependency
  manifests, or to audit whether a branch silently fixes
  an advisory.
compatibility: >
  Requires gh CLI (or gish when available) with
  `security_events` read scope for the alerts API.
  Requires git CLI. Optional: python for PEP-440 version
  comparison.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[<PR#>] [--base <branch>]"
disable-model-invocation: true
allowed-tools:
  - Bash(gh *)
  - Bash(git *)
  - Bash(python *)
  - Bash(python3 *)
  - Read
  - Grep
  - Glob
---

Cross-check a branch's dependency bumps against a repo's
open dependabot alerts and bot PRs, surfacing
`supersedes #N` / `resolves alert #M` relationships that
should be recorded in the PR description.

The motivating case: a feature branch bumps `pytest` to
clear a capture bug, *incidentally* crossing the patched
version of an open security advisory — but nobody links
the advisory or closes the redundant dependabot bump PR,
so the alert lingers and the bot PR rots. This skill makes
that linkage explicit and machine-found instead of relying
on a human to remember.

## 0. Resolve scope

- Resolve the PR / base ref:
  - If a `<PR#>` arg is given, pivot to its
    `headRefName` (same hard rule as `/pr-msg` step 2 —
    the PR head is authoritative, NOT local `HEAD`).
  - Else use the current branch; `--base` overrides the
    base branch (default `main`).
- Derive `OWNER/REPO` from `git remote -v` (prefer
  `github`/`origin`).

## 1. Extract the branch's dependency bumps

Diff the dependency manifests between base and head and
pull out `(package, old → new)` triples:

```bash
git diff <base>..<head> -- \
  pyproject.toml uv.lock requirements*.txt \
  setup.cfg setup.py package.json
```

- For `pyproject.toml`: capture constraint changes
  (`"pytest>=9.0"` → `"pytest>=9.0.3"`), noting the new
  *floor*.
- For lockfiles (`uv.lock`, `package-lock.json`, …):
  capture the *pinned* version (`version = "9.1.0"`),
  which is what scanners actually read.
- Keep BOTH where present — the floor and the pin can
  disagree (see pass 3's lock-mismatch check).

## 2. Fetch open dependabot alerts

```bash
gh api repos/<owner>/<repo>/dependabot/alerts \
  --jq '[.[] | select(.state=="open") | {
    number,
    pkg: .dependency.package.name,
    manifest: .dependency.manifest_path,
    vulnerable: .security_advisory.vulnerabilities[0].vulnerable_version_range,
    patched: .security_advisory.vulnerabilities[0].first_patched_version.identifier,
    severity: .security_advisory.severity,
    ghsa: .security_advisory.ghsa_id,
    cve: .security_advisory.cve_id
  }]'
```

If the API 404s/403s, the token lacks `security_events`
read scope — `log()` that clearly and continue with the
bot-PR pass (don't silently drop alert coverage).

## 3. Fetch open dependabot PRs

```bash
gh pr list --repo <owner>/<repo> --state open \
  --app dependabot \
  --json number,title,headRefName
```

Parse each bot PR's `(package, target-version)` from its
title (`Bump <pkg> from <old> to <new>`) or head ref
(`dependabot/<eco>/<pkg>-<new>`).

## 4. Cross-match

For each branch bump from pass 1, against passes 2 & 3:

- **Resolves an alert** when the branch's *effective
  installed version* for `pkg` is `>=` the alert's
  `first_patched_version` AND the alert's `manifest`
  matches a manifest the branch changed.
  - "effective installed version" = the **lockfile pin**
    when a lock exists (scanners read the lock), else the
    constraint floor.
- **Supersedes a bot PR** when the branch's target
  version for `pkg` is `>=` the bot PR's target version.

Use PEP-440 / semver comparison, not string compare
(`9.1.0` vs `9.0.3`):

```bash
python -c "from packaging.version import Version as V; \
  import sys; print(V(sys.argv[1]) >= V(sys.argv[2]))" \
  9.1.0 9.0.3
```

### Lock-mismatch guard (the load-bearing check)

Flag the case where the constraint *floor* is bumped past
the advisory but the **committed lockfile is still
vulnerable** (e.g. `pyproject` says `>=9.0.3` but
`uv.lock` still pins `8.3.5`). Dependabot reads the lock,
so the alert will NOT auto-close until the lock is
regenerated. Emit this as a `⚠ needs relock` action, not
a clean "resolves".

## 5. Present findings

Group as ready-to-paste lines for the PR `### Links` /
`### Related` section:

```
### Links

- supersedes #<N> — dependabot's `<pkg>` <old>→<new> bump
  (this branch carries it inline).
- resolves dependabot alert #<M> / <CVE-id> (`<pkg>`
  <vulnerable>), patched in <patched>.
  * <advisory-url>
```

For each finding also note the *follow-through* action so
it isn't forgotten:

- `merge auto-closes alert #M` (lock carries the pin), OR
- `⚠ relock needed before alert #M clears`, OR
- `close bot PR #N after this merges` (offer to do it via
  `gh pr close #N --comment "superseded by #<this>"`).

## 6. Hand off to `/pr-msg`

These findings are exactly the candidates `/pr-msg`'s
"Related issues & PRs" step prompts about. Two modes:

- **Invoked from `/pr-msg`**: return the findings so the
  Links pass can fold them in (and the CVE/advisory URL
  into a `* <url>` sub-bullet).
- **Invoked standalone**: present the block to the user
  and, on confirmation, run `/pr-msg <PR#>` in update
  mode to splice the Links section.

Never auto-edit the PR body or close bot PRs without
explicit user confirmation — surface, then act.

## Caveats

- The alerts API is private + scope-gated; a missing
  scope must be reported, never silently skipped.
- Version ranges can be ecosystem-specific; default to
  PEP-440 for Python, semver for npm. When unsure about a
  range, flag as "review manually" rather than asserting.
- Manifest matching matters: an alert on `uv.lock` is
  only resolved by a change that lands in `uv.lock`, not
  by a `pyproject.toml` floor bump alone (see pass 4).
