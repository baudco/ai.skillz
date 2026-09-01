#!/usr/bin/env python3
"""Pre-merge commit-linking pass for `/pr-msg` bodies.

The simplified pr-msg format keeps the working PR body hash-free
(grouped feature bullets, no per-commit ref ceremony). Right before
the PR is actually merged, run this to append a `### Commit index`
section — one `([short][short]) <subject>` line per commit plus the
reference-link definitions — so the merged description carries
clickable provenance without polluting every earlier revision.

Usage:

    python linkify-commits.py main..HEAD >> body.md
    python linkify-commits.py main..feature-branch \
        --repo-url https://github.com/owner/repo > index.md

Then sync: `gh pr edit <num> --body-file body.md`.

The commit-subject lines are exempt from the 69-col fill rule the
same way ref-link defs are: only the *rendered* text counts and
subjects are already <=50ish cols.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def detect_repo_url() -> str:
    """Derive the https commit-link base from `git remote -v`."""
    remotes = sh('git', 'remote', '-v')
    # preference order mirrors SKILL.md: github/origin first
    for prefer in ('github', 'origin'):
        for line in remotes.splitlines():
            name, url, *_ = line.split()
            if name != prefer:
                continue
            m = re.match(
                r'(?:git@|https://)([^:/]+)[:/]([^/]+)/(.+?)(?:\.git)?$',
                url,
            )
            if m:
                host, owner, repo = m.groups()
                return f'https://{host}/{owner}/{repo}'
    sys.exit('linkify-commits: no parseable github/origin remote')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('range', help='git rev range, e.g. main..HEAD')
    p.add_argument(
        '--repo-url',
        help='https base (default: derived from git remotes)',
    )
    args = p.parse_args()

    base = (args.repo_url or detect_repo_url()).rstrip('/')
    log = sh(
        'git', 'log', '--reverse', '--format=%H %h %s', args.range,
    )
    if not log:
        sys.exit(f'linkify-commits: no commits in {args.range}')

    rows = [line.split(' ', 2) for line in log.splitlines()]

    out = ['---', '', '### Commit index', '']
    for _, short, subject in rows:
        out.append(f'- ([{short}][{short}]) {subject}')
    out.append('')
    for full, short, _ in rows:
        out.append(f'[{short}]: {base}/commit/{full}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
