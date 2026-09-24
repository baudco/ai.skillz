# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Check name-based resume selection without starting real harnesses.

'''

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aiskillz import _resume
from aiskillz.cli import resume_main


@pytest.mark.parametrize(
    ('harness', 'argv'),
    [
        ('codex', ['codex', 'resume', 'dialog-id']),
        ('opencode', ['opencode', '--session', 'dialog-id']),
        ('claude', ['claude', '--resume', 'dialog-id']),
    ],
)
def test_resume_name_routes_to_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
    argv: list[str],
) -> None:
    '''
    A name is meaningful only with its harness dialog ID.

    Feed one exact saved name from a temporary directory. Assert
    that each installed CLI form receives the ID, not the name,
    while the selected directory remains the process cwd.

    '''
    record: dict = {
        'name': 'Build feature',
        'id': 'dialog-id',
        'harness': harness,
        'cwd': str(tmp_path),
    }
    listing: Mock = Mock(return_value=[record])
    monkeypatch.setattr(_resume.dialogs, 'list_dialogs', listing)
    target: dict = _resume.resume_target(
        'Build feature', repo=str(tmp_path),
    )
    assert target['argv'] == argv
    assert target['cwd'] == str(tmp_path)
    assert listing.call_args.kwargs['path'] == str(tmp_path)
    _resume.resume_target('Build feature')
    assert listing.call_args.kwargs['path'] == '.'
    _resume.resume_target('Build feature', all_repos=True)
    assert listing.call_args.kwargs['path'] is None


def test_duplicate_name_requires_explicit_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    Two harnesses can assign the same name to different dialogs.

    Return both records for one directory. The resolver must not
    pick the newest or first result, and an ID can select one.

    '''
    rows: list[dict] = [
        {
            'name': 'Shared', 'id': 'one',
            'harness': 'codex', 'cwd': str(tmp_path),
        },
        {
            'name': 'Shared', 'id': 'two',
            'harness': 'opencode', 'cwd': str(tmp_path),
        },
    ]
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        lambda **kwargs: rows,
    )
    with pytest.raises(ValueError, match='ambiguous'):
        _resume.resume_target('Shared')
    target: dict = _resume.resume_target(
        'Shared', dialog_id='two',
    )
    assert target['argv'] == ['opencode', '--session', 'two']


def test_copied_short_name_must_identify_one_dialog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    The table shortens long names that users may copy verbatim.

    Give two dialogs the same 35-character prefix. The visible
    label must be accepted for a unique record, then refused once
    another dialog shares that label.

    '''
    prefix: str = 'x' * 35
    rows: list[dict] = [{
        'name': prefix + ' first',
        'id': 'one',
        'harness': 'codex',
        'cwd': str(tmp_path),
    }]
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        lambda **kwargs: rows,
    )
    label: str = prefix + '…'
    assert _resume.resume_target(label)['id'] == 'one'
    rows.append({
        'name': prefix + ' second',
        'id': 'two',
        'harness': 'claude',
        'cwd': str(tmp_path),
    })
    with pytest.raises(ValueError, match='ambiguous'):
        _resume.resume_target(label)


def test_recorded_wkt_or_explicit_cwd_controls_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    A dialog may start in main and later move to a linked WKT.

    Supply a recorded WKT path and verify it wins over saved cwd.
    Several paths must require an explicit override instead of
    launching the wrong worktree.

    '''
    wkt: Path = tmp_path / 'feature'
    wkt.mkdir()
    other: Path = tmp_path / 'other'
    other.mkdir()
    row: dict = {
        'name': 'Feature', 'id': 'id',
        'harness': 'codex', 'cwd': str(tmp_path),
    }
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        lambda **kwargs: [row],
    )
    lookup: Mock = Mock(return_value={str(wkt)})
    monkeypatch.setattr(_resume.WktLookup, 'roots', lookup)
    assert _resume.resume_target('Feature')['cwd'] == str(wkt)
    lookup.return_value = {str(wkt), str(other)}
    with pytest.raises(ValueError, match='Several WKTs'):
        _resume.resume_target('Feature')
    assert _resume.resume_target(
        'Feature', cwd=str(other),
    )['cwd'] == str(other)


def test_dry_run_previews_without_starting_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    '''
    A name lookup can be reviewed before launching a harness.

    Supply a fixed target and run the CLI in dry-run mode. The
    printed JSON must contain its cwd and argv, while no child
    process is created.

    '''
    target: dict = {
        'name': 'Feature', 'id': 'id',
        'harness': 'codex', 'cwd': str(tmp_path),
        'argv': ['codex', 'resume', 'id'],
    }
    resolver: Mock = Mock(return_value=target)
    monkeypatch.setattr('aiskillz.cli.resume_target', resolver)
    launch: Mock = Mock()
    monkeypatch.setattr('aiskillz.cli.subprocess.run', launch)
    assert resume_main(['Feature', '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out) == target
    assert resolver.call_args.kwargs['repo'] == '.'
    assert resolver.call_args.kwargs['all_repos'] is False
    assert resume_main(['Feature', '-a', '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out) == target
    assert resolver.call_args.kwargs['all_repos'] is True
    launch.assert_not_called()


def test_resume_launches_exact_argv_and_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    A named dialog must spawn only its selected harness process.

    Mock the executable lookup and child runner. The CLI passes a
    list of arguments without shell interpolation and returns the
    harness exit status to the caller.

    '''
    target: dict = {
        'name': 'Feature', 'id': 'id',
        'harness': 'claude', 'cwd': str(tmp_path),
        'argv': ['claude', '--resume', 'id'],
    }
    monkeypatch.setattr(
        'aiskillz.cli.resume_target',
        lambda *args, **kwargs: target,
    )
    monkeypatch.setattr(
        'aiskillz.cli.shutil.which', lambda name: '/bin/claude',
    )
    launch: Mock = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr('aiskillz.cli.subprocess.run', launch)
    assert resume_main(['Feature']) == 7
    launch.assert_called_once_with(
        ['claude', '--resume', 'id'],
        cwd=str(tmp_path),
        check=False,
    )
