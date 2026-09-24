# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.


'''
Check Git layouts used to anchor shared worktree associations.

'''

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from aiskillz.git import repository, primary_worktree
from aiskillz.wkt._relations import relation_dir


@pytest.mark.skipif(
    not shutil.which('git'), reason='git unavailable',
)
@pytest.mark.parametrize('layout', ['normal', 'bare', 'separate'])
def test_shared_anchor_across_git_layouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
) -> None:
    '''
    Per-checkout state would split associations across worktrees.

    Construct normal, bare and separate-Git-dir repositories with a
    linked checkout. Query through both paths while inherited GIT_DIR
    points elsewhere. Both must find the same Git metadata and shared
    .ai directory without creating association files. Removing the
    checkout must remove it from the live inventory while preserving
    the repository's shared directory anchor. Separate Git metadata
    needs core.worktree: without it Git reports its metadata path
    itself, which must be rejected rather than used as a checkout.

    '''
    main: Path = tmp_path / 'main'
    common: Path = main / '.git'
    args: list[str] = ['git', 'init', '--quiet']
    if layout == 'bare':
        args.append('--bare')
        common = main
    elif layout == 'separate':
        common = tmp_path / 'git-data'
        args.extend(['--separate-git-dir', str(common)])
    subprocess.run(
        [*args, str(main)], check=True, capture_output=True,
    )
    if layout == 'separate':
        with pytest.raises(ValueError, match='set core.worktree'):
            relation_dir(common)
        subprocess.run(
            ['git', '-C', str(main), 'config',
             'core.worktree', str(main)],
            check=True, capture_output=True,
        )
    linked: Path = tmp_path / 'linked'
    linked.mkdir()
    private: Path = common / 'worktrees/linked'
    private.mkdir(parents=True)
    (private / 'HEAD').write_text('ref: refs/heads/fixture\n')
    (private / 'commondir').write_text('../..\n')
    (private / 'gitdir').write_text(str(linked / '.git') + '\n')
    (linked / '.git').write_text(f'gitdir: {private}\n')
    monkeypatch.setenv('GIT_DIR', str(tmp_path / 'wrong-git-dir'))
    checkout: Path
    for checkout in (main, linked):
        resolved: Path
        inventory: dict[str, str]
        resolved, inventory = repository(str(checkout))
        assert resolved == common
        assert inventory == {str(linked): str(private)}
        assert primary_worktree(resolved) == main
        shared: Path = main / '.ai/state/dialogs'
        assert relation_dir(resolved) == shared
    assert not (main / '.ai').exists()
    assert os.environ['GIT_DIR'].endswith('wrong-git-dir')
    shutil.rmtree(linked)
    assert repository(str(main))[1] == {}
    assert relation_dir(common) == main / '.ai/state/dialogs'
