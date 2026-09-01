# pr-merge.xsh — xonsh aliases for the `/pr-msg` pre-merge
# commit-linking pass.
#
# Source from your xonshrc:
#
#   source /path/to/ai.skillz/skills/pr-msg/pr-merge.xsh
#
# Then from ANY repo with the pr-msg skill deployed (i.e. having a
# `.claude/skills/pr-msg` symlink/dir), or with a global
# `~/.claude/skills/pr-msg`:
#
#   pr-linkify <pr-num> [base-branch]   # append `### Commit index`
#                                       # to the live PR body via gh
#   pr-merge   <pr-num> [base-branch]   # pr-linkify, then
#                                       # `gh pr merge <num>`
#
# The linkify pass is idempotent-guarded: if the body already has a
# `### Commit index` section it refuses to double-append. Requires
# the PR's head branch history locally (fetch first if needed).
import os as _os
import subprocess as _sp
import tempfile as _tmp

def _prmsg_skill_dir():
    try:
        root = _sp.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            text=True,
        ).strip()
    except _sp.CalledProcessError:
        root = ''
    cands = [
        _os.path.join(root, '.claude/skills/pr-msg'),
        _os.path.expanduser('~/.claude/skills/pr-msg'),
    ]
    for cand in cands:
        if root == '' and not cand.startswith(_os.path.expanduser('~')):
            continue
        if _os.path.isdir(cand):
            return _os.path.realpath(cand)
    return None

def _pr_linkify(args):
    if not args:
        print('usage: pr-linkify <pr-num> [base-branch]')
        return 1
    num, base = args[0], (args[1] if len(args) > 1 else 'main')
    skill = _prmsg_skill_dir()
    if skill is None:
        print('pr-linkify: no deployed pr-msg skill found '
              '(.claude/skills/pr-msg or ~/.claude/skills/pr-msg)')
        return 1
    script = _os.path.join(skill, 'scripts', 'linkify-commits.py')
    head = _sp.check_output(
        ['gh', 'pr', 'view', num, '--json', 'headRefName',
         '--jq', '.headRefName'], text=True).strip()
    body = _sp.check_output(
        ['gh', 'pr', 'view', num, '--json', 'body',
         '--jq', '.body'], text=True)
    if '### Commit index' in body:
        print(f'pr-linkify: PR #{num} already has a Commit index — '
              'skipping (edit the body manually to regenerate)')
        return 0
    index = _sp.check_output(
        ['python', script, f'{base}..{head}'], text=True)
    with _tmp.NamedTemporaryFile(
        'w', suffix='.md', delete=False) as f:
        f.write(body.rstrip('\n') + '\n\n' + index)
        tmp = f.name
    _sp.check_call(['gh', 'pr', 'edit', num, '--body-file', tmp])
    _os.unlink(tmp)
    print(f'pr-linkify: appended Commit index ({base}..{head}) '
          f'to PR #{num}')
    return 0

def _pr_merge(args):
    if not args:
        print('usage: pr-merge <pr-num> [base-branch] [gh merge flags…]')
        return 1
    rc = _pr_linkify(args[:2])
    if rc != 0:
        return rc
    extra = args[2:] if len(args) > 1 else []
    return _sp.call(['gh', 'pr', 'merge', args[0], *extra])

aliases['pr-linkify'] = _pr_linkify
aliases['pr-merge'] = _pr_merge
