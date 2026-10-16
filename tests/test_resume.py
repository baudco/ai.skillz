# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Check name and ID resume selection without starting real harnesses.

'''

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aiskillz import _resume
from aiskillz.cli import resume_main


@pytest.mark.parametrize(
    'selector', ['Build feature', 'dialog-id'],
)
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
    selector: str,
) -> None:
    '''
    Names and IDs must resolve to the same harness command.

    Feed one dialog from a temporary directory and select it by
    either name or ID. Assert each CLI receives its ID and that
    both selectors preserve cwd filtering and all-repo opt-in.

    '''
    record: dict = {
        'name': 'Build feature',
        'id': 'dialog-id',
        'harness': harness,
        'cwd': str(tmp_path),
    }
    listing: Mock = Mock(return_value=[record])
    monkeypatch.setattr(_resume.dialogs, 'list_dialogs', listing)
    probe: Mock = Mock(return_value=False)
    monkeypatch.setattr(
        _resume, 'codex_supports_no_daemon', probe,
    )
    target: dict = _resume.resume_target(
        selector, repo=str(tmp_path),
    )
    assert target['argv'] == argv
    assert target['cwd'] == str(tmp_path)
    assert listing.call_args.kwargs['path'] == str(tmp_path)
    _resume.resume_target(selector)
    assert listing.call_args.kwargs['path'] == '.'
    _resume.resume_target(selector, all_repos=True)
    assert listing.call_args.kwargs['path'] is None
    probe.assert_not_called()


def test_resume_id_precedes_name_and_refuses_id_collisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    '''
    Treating every selector as a name could launch the wrong dialog.

    Give one dialog an ID that another uses as its name. The CLI
    dry run must select the exact ID. Then add a cross-harness ID
    collision: refuse it until a harness filter narrows the result.
    A conflicting --id must fail instead of falling back to a name.

    '''
    rows: list[dict] = [
        {
            'name': 'Actual dialog', 'id': 'shared-id',
            'harness': 'opencode', 'cwd': str(tmp_path),
        },
        {
            'name': 'shared-id', 'id': 'other-id',
            'harness': 'claude', 'cwd': str(tmp_path),
        },
    ]

    def listing(**kwargs) -> list[dict]:
        '''
        Supply the requested harness scope to resume selection.

        '''
        return [
            row for row in rows
            if kwargs['harness'] in (None, row['harness'])
        ]

    monkeypatch.setattr(_resume.dialogs, 'list_dialogs', listing)
    monkeypatch.setattr(
        _resume.WktLookup, 'roots', lambda *args: set(),
    )
    assert resume_main(['shared-id', '--dry-run']) == 0
    target: dict = json.loads(capsys.readouterr().out)
    assert target['name'] == 'Actual dialog'
    assert target['argv'] == ['opencode', '--session', 'shared-id']
    with pytest.raises(ValueError, match='No dialog matching'):
        _resume.resume_target('shared-id', dialog_id='other-id')

    rows.append({
        'name': 'Collision', 'id': 'shared-id',
        'harness': 'claude', 'cwd': str(tmp_path),
    })
    with pytest.raises(ValueError, match='ambiguous'):
        _resume.resume_target('shared-id')
    target = _resume.resume_target('shared-id', harness='claude')
    assert target['argv'] == ['claude', '--resume', 'shared-id']


@pytest.mark.parametrize(
    ('help_text', 'returncode', 'expected'),
    [
        ('      --no-daemon\n', 0, True),
        ('      --last\n', 0, False),
        ('      --no-daemon\n', 1, False),
    ],
)
def test_codex_resume_probes_help_for_no_daemon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    help_text: str,
    returncode: int,
    expected: bool,
) -> None:
    '''
    Codex installations differ in daemon flag support.

    Mock the installed CLI's resume help with and without the
    option, including failed help. `ai.resume --dry-run` must show
    the same argv a real launch would receive, with the flag only
    when a successful help response advertises it.

    '''
    record: dict = {
        'name': 'Feature',
        'id': 'dialog-id',
        'harness': 'codex',
        'cwd': str(tmp_path),
    }
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        lambda **kwargs: [record],
    )
    monkeypatch.setattr(
        _resume.WktLookup, 'roots',
        lambda *args: set(),
    )
    probe: Mock = Mock(return_value=SimpleNamespace(
        returncode=returncode,
        stdout=help_text,
        stderr='',
    ))
    monkeypatch.setattr(_resume.subprocess, 'run', probe)

    assert resume_main(['Feature', '--dry-run']) == 0
    target: dict = json.loads(capsys.readouterr().out)
    argv: list[str] = ['codex', 'resume']
    if expected:
        argv.append('--no-daemon')
    argv.append('dialog-id')
    assert target['argv'] == argv
    probe.assert_called_once_with(
        ['codex', 'resume', '--help'],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def test_public_resolution_never_probes_a_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    Workspace previews must not spawn a harness capability probe.

    The old resolver executed codex resume --help as part of argv
    construction. Resolve an exact ID with explicit task cwd while
    subprocess.run raises on any invocation. Assert the saved cwd
    remains distinct and capabilities affect argv only when supplied
    explicitly by the caller.

    '''
    from aiskillz import resume_target

    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        Mock(return_value=[{
            'name': 'Exact title',
            'id': 'dialog-id',
            'harness': 'codex',
            'cwd': str(tmp_path / 'old-directory'),
        }]),
    )
    process: Mock = Mock(side_effect=AssertionError('spawned'))
    monkeypatch.setattr(_resume.subprocess, 'run', process)
    target: dict = resume_target(
        'dialog-id', harness='codex', cwd=str(tmp_path),
    )
    assert target['cwd'] == str(tmp_path)
    assert target['saved_cwd'] == str(tmp_path / 'old-directory')
    assert target['argv'] == ['codex', 'resume', 'dialog-id']
    target = resume_target(
        'dialog-id', harness='codex', cwd=str(tmp_path),
        codex_no_daemon=True,
    )
    assert '--no-daemon' in target['argv']
    process.assert_not_called()



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
    Several paths must warn and use saved cwd rather than block
    resume or choose an arbitrary worktree. --cwd still overrides.

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
    target: dict = _resume.resume_target('Feature')
    assert target['cwd'] == str(tmp_path)
    assert 'Several WKTs' in target['warnings'][0]
    assert _resume.resume_target(
        'Feature', cwd=str(other),
    )['cwd'] == str(other)


@pytest.mark.parametrize(
    'failure',
    [
        ValueError('Malformed relation file'),
        OSError('Cannot read relation file'),
    ],
)
def test_wkt_metadata_failure_cannot_block_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    failure: Exception,
) -> None:
    '''
    Optional WKT lookup used to prevent an otherwise valid resume.

    Make `WktLookup.roots()` raise for corrupt or unreadable relation
    metadata while the dialog's saved cwd still exists. The CLI
    must launch the selected harness there, report the metadata
    warning and return its exit status. An explicit --cwd bypasses
    lookup entirely and does not emit a metadata warning.

    '''
    row: dict = {
        'name': 'Feature',
        'id': 'dialog-id',
        'harness': 'claude',
        'cwd': str(tmp_path),
    }
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        Mock(return_value=[row]),
    )
    lookup: Mock = Mock(side_effect=failure)
    monkeypatch.setattr(_resume.WktLookup, 'roots', lookup)
    monkeypatch.setattr(
        'aiskillz.cli.shutil.which',
        Mock(return_value='/bin/claude'),
    )
    launch: Mock = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr('aiskillz.cli.subprocess.run', launch)
    assert resume_main(['Feature']) == 0
    launch.assert_called_once_with(
        ['claude', '--resume', 'dialog-id'],
        cwd=str(tmp_path),
        check=False,
    )
    assert str(failure) in capsys.readouterr().err
    lookup.reset_mock()
    target: dict = _resume.resume_target(
        'Feature', cwd=str(tmp_path),
    )
    assert 'warnings' not in target
    lookup.assert_not_called()


def test_missing_recorded_directory_uses_saved_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    A recorded directory can disappear after Git lookup verifies it.

    Return a nonexistent WKT from `WktLookup.roots()` with an
    existing saved cwd. The resolver must warn and use saved cwd,
    preserving optional indexing even when metadata checks race
    with worktree teardown. If saved cwd is also gone, the remaining
    failure concerns the launch directory and suggests --cwd.

    '''
    missing: Path = tmp_path / 'gone'
    row: dict = {
        'name': 'Feature',
        'id': 'dialog-id',
        'harness': 'claude',
        'cwd': str(tmp_path),
    }
    monkeypatch.setattr(
        _resume.dialogs, 'list_dialogs',
        Mock(return_value=[row]),
    )
    monkeypatch.setattr(
        _resume.WktLookup, 'roots',
        Mock(return_value={str(missing)}),
    )
    target: dict = _resume.resume_target('Feature')
    assert target['cwd'] == str(tmp_path)
    assert str(missing) in target['warnings'][0]
    row['cwd'] = str(missing)
    with pytest.raises(ValueError, match='Use --cwd'):
        _resume.resume_target('Feature')


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
    monkeypatch.setattr(
        'aiskillz.cli.codex_supports_no_daemon',
        Mock(return_value=False),
    )
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
