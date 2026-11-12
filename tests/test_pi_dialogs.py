# Copyright (C) 2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise Pi discovery, exact resume and shared WKT CLI operations.

'''

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import BinaryIO, TextIO
from unittest.mock import Mock, patch

import pytest

from aiskillz import (
    get_dialog,
    list_dialogs,
    name2id,
    preview_wkt_relations,
    resume_target,
    list_wkt_relations,
    save_wkt_preview,
)
from aiskillz.cli import main, resume_main
from aiskillz.dialogs._inspect import observations
from aiskillz.dialogs._pi import pi_sessions
from aiskillz._completion import complete_resume
from xonsh.built_ins import XSH
from xonsh.parsers.completion_context import (
    CompletionContext,
    CompletionContextParser,
)


@pytest.fixture
def pi_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    '''
    Isolate every store; implicit discovery must not read user logs.

    '''
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex'))
    monkeypatch.setenv('OPENCODE_DATA_DIR', str(tmp_path / 'oc'))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'claude'))
    monkeypatch.setenv('PI_CODING_AGENT_DIR', str(tmp_path / 'pi'))
    monkeypatch.delenv('PI_CODING_AGENT_SESSION_DIR', raising=False)
    store: Path = tmp_path / 'pi/sessions'
    store.mkdir(parents=True)
    return store


def session(
    store: Path,
    cwd: Path,
    did: str = 'full-dialog-id',
    name: str = 'Pi work',
    bucket: str = 'bucket',
) -> Path:
    '''
    Write a native header with a name independent of its filename.

    '''
    directory: Path = store / bucket
    directory.mkdir(parents=True, exist_ok=True)
    path: Path = directory / (did.replace('/', '_') + '.jsonl')
    events: list[dict] = [
        {
            'type': 'session',
            'version': 3,
            'id': did,
            'cwd': str(cwd),
        },
        {'type': 'session_info', 'name': name},
    ]
    stream: TextIO
    with path.open('w') as stream:
        event: dict
        for event in events:
            stream.write(json.dumps(event) + '\n')

    return path


def test_pi_metadata_lookup_and_source_only_cli(
    pi_store: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    '''
    Prove native Pi metadata is reachable through the public CLI.

    - Regression: `list_dialogs()` and CLI choices omitted Pi.
    - Regression: Python accepts `NaN` where Pi rejects the event;
      such a later rename must not override valid native metadata.
    - Arrange: surround a rename and model change with corrupt and
      non-object events in a named native session.
    - Proof: `get_dialog()`, `name2id()` and `main()` agree on the
      exact header ID and saved metadata, not filename guesses.
    - Proof: `resume_main()` dry-run pins the native session file;
      source invocation from an unrelated cwd finds the same record
      without starting Pi.

    '''
    path: Path = session(pi_store, tmp_path)
    stream: BinaryIO
    with path.open('ab') as stream:
        stream.write(b'null\n{bad\n\xff\n')
        stream.write(json.dumps({
            'type': 'session_info',
            'name': 'Renamed dialog',
        }).encode() + b'\n')
        stream.write(json.dumps({
            'type': 'model_change',
            'provider': 'provider',
            'modelId': 'selected-model',
        }).encode() + b'\n')
        stream.write(
            b'{"type":"session_info","name":"invalid","x":NaN}\n'
        )
    row: dict = get_dialog('full-dialog-id', 'pi')
    assert row['session_file'] == str(path)
    assert row['name'] == 'Renamed dialog'
    assert row['provider'] == 'provider'
    assert row['model'] == 'selected-model'
    assert name2id(tmp_path, 'pi') == {
        'Renamed dialog': 'full-dialog-id',
    }
    assert list_dialogs(tmp_path) == [row]
    assert main([str(tmp_path), '-b', 'pi', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == [row]
    assert resume_main([
        'Renamed dialog', '--repo', str(tmp_path), '-b', 'pi',
        '--dry-run',
    ]) == 0
    target: dict = json.loads(capsys.readouterr().out)
    assert target['argv'] == [
        'pi', '--session', 'full-dialog-id', '--session-dir',
        str(path.parent),
    ]
    source: Path = Path(__file__).resolve().parents[1]
    result: subprocess.CompletedProcess = subprocess.run(
        [sys.executable, str(source / 'aiskillz/cli.py'),
         str(tmp_path), '-b', 'pi', '--json'],
        cwd=tmp_path, env=dict(os.environ),
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == [row]


def test_pi_unsupported_layout_reports_rejected_value(
    pi_store: Path,
) -> None:
    '''
    Identify the rejected discovery layout in caller diagnostics.

    - Regression: the layout failure omitted the caller's bad value,
      leaving configuration mistakes indistinguishable.
    - Arrange: pass an unsupported layout to `pi_sessions()`.
    - Proof: validation still raises, and its message names both the
      Pi store operation and the rejected layout, not a guessed root.

    '''
    error: pytest.ExceptionInfo[ValueError]
    with pytest.raises(ValueError, match='Pi store layout') as error:
        pi_sessions(pi_store, None, session_layout='recursive')

    assert "'recursive'" in str(error.value)


def test_pi_refuses_duplicate_ids_before_scope_or_recency(
    pi_store: Path,
    tmp_path: Path,
) -> None:
    '''
    Reject duplicate IDs before Pi can select another session file.

    - Regression: `list_dialogs()` normally keeps the newest record,
      but Pi's native ID lookup takes the first matching file.
    - Arrange: place one ID in two cwd buckets with distinct saved
      cwds and mtimes, so scope and recency suggest different files.
    - Proof: scoped discovery and `resume_target()` both raise before
      the native CLI can resolve that ambiguity to another file.

    '''
    first: Path = session(pi_store, tmp_path)
    second: Path = session(
        pi_store, tmp_path / 'elsewhere', bucket='other',
    )
    os.utime(first, (1, 1))
    os.utime(second, (2, 2))
    with pytest.raises(ValueError, match='Ambiguous Pi dialog ID'):
        list_dialogs(tmp_path, 'pi')

    with pytest.raises(ValueError, match='Ambiguous Pi dialog ID'):
        resume_target('full-dialog-id', repo=str(tmp_path))


@pytest.mark.parametrize(('field', 'value'), [
    ('version', 99),
    ('cwd', None),
])
def test_pi_counts_ineligible_duplicate_headers_native_can_select(
    pi_store: Path,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    '''
    Count ineligible duplicate headers before native exact lookup.

    - Regression: Pi matches header IDs before checking version/cwd,
      so a duplicate omitted by our listing can still win its search.
    - Arrange: put an unsupported duplicate behind malformed/falsy
      preamble lines that native discovery skips.
    - Proof: `resume_target()` rejects the ambiguity instead of
      launching the healthy-looking file. Counting only eligible
      records would incorrectly let this request succeed.

    '''
    session(pi_store, tmp_path)
    header: dict = {
        'type': 'session',
        'version': 3,
        'id': 'full-dialog-id',
        'cwd': str(tmp_path),
    }
    header[field] = value
    (pi_store / 'bucket/duplicate.jsonl').write_text(
        '\n{bad\nnull\nfalse\n0\nNaN\n'
        + json.dumps(header) + '\n'
    )
    with pytest.raises(ValueError, match='Ambiguous Pi dialog ID'):
        resume_target('full-dialog-id', repo=str(tmp_path))


@pytest.mark.parametrize('version', [None, 1, 2, 3])
def test_pi_supports_native_header_scan_and_versions(
    pi_store: Path,
    tmp_path: Path,
    version: int|None,
) -> None:
    '''
    Find supported native headers behind a skipped preamble.

    - Regression: first-line-only parsing misses sessions that Pi
      accepts after blank, malformed or JSON-falsy scalar lines.
    - Arrange: seed versions 1-3 and legacy missing-version headers
      behind the same skipped preamble.
    - Proof: `list_dialogs()` returns the exact header ID for every
      supported variant, rather than rejecting the physical file.

    '''
    header: dict = {
        'type': 'session',
        'id': 'supported',
        'cwd': str(tmp_path),
    }
    if version is not None:
        header['version'] = version

    (pi_store / 'bucket').mkdir()
    (pi_store / 'bucket/header.jsonl').write_text(
        '\n{bad\nnull\nfalse\n0\nNaN\n'
        + json.dumps(header) + '\n'
    )
    assert list_dialogs(tmp_path, 'pi')[0]['id'] == 'supported'


def test_pi_ambiguous_names_prefixes_and_custom_flat_store(
    pi_store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    Resolve custom-store sessions without prefix or label guesses.

    - Regression: Pi accepts prefixes and first-match selectors;
      forwarding an ambiguous label could resume another session.
    - Arrange: put two equal labels in a flat custom root selected by
      `PI_CODING_AGENT_SESSION_DIR`, overriding the agent home.
    - Proof: `name2id()` retains both labels and `resume_target()`
      rejects duplicate names and ID prefixes.
    - Proof: an explicit exact ID resolves the intended file and pins
      its flat directory, without treating it as a cwd bucket.

    '''
    custom: Path = tmp_path / 'flat store'
    one: Path = session(custom, tmp_path, did='one', bucket='')
    session(custom, tmp_path, did='only', bucket='')
    monkeypatch.setenv('PI_CODING_AGENT_SESSION_DIR', str(custom))
    assert len(name2id(tmp_path, 'pi')) == 2
    with pytest.raises(ValueError, match='ambiguous'):
        resume_target('Pi work', repo=str(tmp_path), harness='pi')

    with pytest.raises(ValueError, match='No dialog matching'):
        resume_target('on', repo=str(tmp_path), harness='pi')

    target: dict = resume_target(
        'Pi work', repo=str(tmp_path), harness='pi', dialog_id='one',
    )
    assert get_dialog('one', 'pi')['session_file'] == str(one)
    assert target['argv'] == [
        'pi', '--session', 'one', '--session-dir', str(custom),
    ]


def test_pi_layout_controls_the_entire_discovery_scope(
    pi_store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    Keep default and custom discovery layouts as separate scopes.

    - Regression: a root path alone cannot identify whether Pi uses
      cwd buckets or a flat custom session directory.
    - Arrange: place distinct IDs at both depths below the same root,
      then toggle `PI_CODING_AGENT_SESSION_DIR` for that root.
    - Proof: `list_dialogs()` exposes only the configured depth. It
      neither merges layout scopes nor treats an internal CLI bucket
      pin as caller configuration.

    '''
    session(pi_store, tmp_path, did='bucketed')
    session(pi_store, tmp_path, did='flat', bucket='')
    rows: list[dict] = list_dialogs(tmp_path, 'pi')
    assert len(rows) == 1
    assert rows[0]['id'] == 'bucketed'
    monkeypatch.setenv('PI_CODING_AGENT_SESSION_DIR', str(pi_store))
    rows = list_dialogs(tmp_path, 'pi')
    assert len(rows) == 1
    assert rows[0]['id'] == 'flat'


@pytest.mark.parametrize('header', [
    None,
    {'type': 'session', 'version': 99, 'id': 'x', 'cwd': '/x'},
    {'type': 'session', 'version': 3, 'id': [], 'cwd': '/x'},
    {'type': 'session', 'version': 3, 'id': 'x', 'cwd': 'relative'},
])
def test_pi_skips_invalid_headers_and_preserves_later_files(
    pi_store: Path,
    tmp_path: Path,
    header: object,
) -> None:
    '''
    Skip invalid headers without hiding healthy neighboring files.

    - Regression: malformed or newer metadata cannot establish a
      supported native ID, even if its filename appears usable.
    - Arrange: place each unsupported header shape beside a healthy
      named session in the same cwd bucket.
    - Proof: `pi_sessions()` returns only the healthy record,
      regardless of ordering; bad headers borrow no filename/event
      identity and do not prevent later files from being scanned.

    '''
    (pi_store / 'bucket').mkdir()
    (pi_store / 'bucket/broken.jsonl').write_text(
        json.dumps(header) + '\n',
    )
    session(pi_store, tmp_path)
    rows: list[dict] = pi_sessions(pi_store, None)
    assert len(rows) == 1
    assert rows[0]['id'] == 'full-dialog-id'


def test_pi_name_fallback_rename_reset_and_escaping_symlink(
    pi_store: Path,
    tmp_path: Path,
) -> None:
    '''
    Bound fallback names and reject outside-store session symlinks.

    - Contract: names are optional display metadata, not native IDs.
    - Arrange: reset a saved name after a long user text block, then
      append a malformed tail to that session file.
    - Proof: `pi_sessions()` uses the bounded first-prompt fallback
      despite the corrupt tail and the explicit empty rename.
    - Failure proof: an escaping symlink raises instead of publishing
      an outside-store file or silently following another root.
    - Diagnostics: the error identifies the rejected path and store.

    '''
    path: Path = session(pi_store, tmp_path)
    stream: TextIO
    with path.open('a') as stream:
        stream.write(json.dumps({
            'type': 'message',
            'message': {
                'role': 'user',
                'content': [{'type': 'text', 'text': 'a' * 200}],
            },
        }) + '\n')
        stream.write('{"type":"session_info","name":""}\n{bad')

    assert pi_sessions(pi_store, None)[0]['name'] == 'a' * 120
    outside: Path = tmp_path / 'outside.jsonl'
    outside.write_text(path.read_text())
    (pi_store / 'bucket/escape.jsonl').symlink_to(outside)
    error: pytest.ExceptionInfo[ValueError]
    with pytest.raises(ValueError, match='escapes store') as error:
        pi_sessions(pi_store, None)

    assert repr(str(pi_store)) in str(error.value)
    assert repr(str(pi_store / 'bucket/escape.jsonl')) in str(
        error.value,
    )


def test_pi_cwd_override_and_recorded_wkt_do_not_fork(
    pi_store: Path,
    tmp_path: Path,
) -> None:
    '''
    Keep Pi resume in its saved cwd without silently forking.

    - Regression: Pi restores saved cwd; a conflicting launch cwd can
      offer to fork instead of continuing the same native ID.
    - Arrange: make `WktLookup.roots()` return another existing cwd.
    - Proof: `resume_target()` warns and retains saved cwd for an
      implicit relation, but rejects an explicit incompatible cwd.
    - Diagnostics: the error names the dialog and both cwd values.

    '''
    session(pi_store, tmp_path)
    other: Path = tmp_path / 'other'
    other.mkdir()
    with patch('aiskillz._resume.WktLookup.roots', return_value={
        str(other),
    }):
        target: dict = resume_target(
            'full-dialog-id', repo=str(tmp_path), harness='pi',
        )

    assert target['cwd'] == str(tmp_path)
    assert 'not forking' in '\n'.join(target['warnings'])
    error: pytest.ExceptionInfo[ValueError]
    with pytest.raises(
        ValueError, match='incompatible --cwd',
    ) as error:
        resume_target(
            'full-dialog-id', repo=str(tmp_path), harness='pi',
            cwd=str(other),
        )

    assert 'full-dialog-id' in str(error.value)
    assert repr(str(other)) in str(error.value)
    assert repr(str(tmp_path)) in str(error.value)


@pytest.mark.parametrize('did', [
    '-flag', 'prefix/path', 'windows\\path', 'file.jsonl', 'bad\nID',
])
def test_pi_rejects_ids_native_cli_would_parse_as_paths_or_flags(
    pi_store: Path,
    tmp_path: Path,
    did: str,
) -> None:
    '''
    Refuse native IDs that Pi would parse as paths or CLI options.

    - Regression: Pi treats slash/backslash and `.jsonl` selectors as
      paths; flag-like or control-bearing IDs are unsafe arguments.
    - Arrange: preserve each synthetic ID in an otherwise valid
      native header, so discovery itself can read the record.
    - Proof: `resume_target()` raises before publishing unsafe argv;
      header identity cannot become a path lookup or option.

    '''
    session(pi_store, tmp_path, did=did)
    with pytest.raises(ValueError, match='ID.*(invalid|path)'):
        resume_target(did, repo=str(tmp_path), harness='pi')


def test_pi_missing_saved_cwd_cannot_be_replaced_by_override(
    pi_store: Path,
    tmp_path: Path,
) -> None:
    '''
    Refuse to replace a missing saved Pi cwd with another directory.

    - Regression: changing cwd cannot repair native exact resume;
      Pi would fork under an allegedly unchanged identity.
    - Arrange: keep a valid header whose saved directory is absent.
    - Proof: `resume_target()` reports the missing directory, and an
      explicit existing cwd still raises rather than repairing it.

    '''
    session(pi_store, tmp_path / 'missing')
    with pytest.raises(
        ValueError, match='Launch directory is missing',
    ):
        resume_target('full-dialog-id', harness='pi', all_repos=True)

    with pytest.raises(ValueError, match='incompatible --cwd'):
        resume_target(
            'full-dialog-id', harness='pi', all_repos=True,
            cwd=str(tmp_path),
        )


def test_pi_worktree_record_preview_and_completion(
    pi_store: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    '''
    Share Pi metadata across relation writes and Xonsh completion.

    - Regression: `record_wkt_relation()` rejected Pi and
      `preview_wkt_relations()` omitted its reader.
    - Arrange: initialize a disposable repo and linked worktree,
      preview its native ID and apply/record it through `main()`.
    - Proof: relation reads retain that ID and confirm the preview
      against Git registration, not an invented process location.
    - Proof: `complete_resume()` reads the same shell-configured
      store without launching Pi or mutating user task states.

    '''
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    subprocess.run([
        'git', '-C', str(tmp_path), '-c', 'user.name=Test',
        '-c', 'user.email=test@example.invalid',
        '-c', 'commit.gpgsign=false',
        'commit', '--allow-empty', '-qm', 'fixture',
    ], check=True)
    linked: Path = tmp_path / 'linked'
    subprocess.run([
        'git', '-C', str(tmp_path), 'worktree', 'add', '-qb',
        'fixture-linked', str(linked),
    ], check=True)
    session(pi_store, linked)
    proposal: dict = preview_wkt_relations(str(tmp_path))
    assert len(proposal['entries']) == 1
    assert proposal['entries'][0]['harness'] == 'pi'
    preview: Path
    digest: str
    preview, digest = save_wkt_preview(proposal)
    assert main([
        'index', str(tmp_path), '--apply', str(preview),
        '--sha256', digest,
    ]) == 0
    assert main([
        'index', str(tmp_path), '--record', 'pi', 'full-dialog-id',
        '--worktree', str(linked),
    ]) == 0
    capsys.readouterr()
    rows: list[dict] = list_wkt_relations(str(tmp_path), 'pi')
    assert rows[0]['id'] == 'full-dialog-id'
    assert rows[0]['git_active'] is True
    assert preview_wkt_relations(str(tmp_path))['confirmed'] == 1

    line: str = 'ai.resume --repo ' + str(linked) + ' -b pi Pi'
    context: CompletionContext = CompletionContextParser().parse(
        line, len(line),
    )
    shell: SimpleNamespace = SimpleNamespace(
        detype=lambda: dict(os.environ),
    )
    with patch.object(XSH, 'env', shell):
        result: tuple = complete_resume(context)

    assert len(result[0]) == 1
    assert result[0][0].display == 'Pi work'


def test_pi_pruned_evidence_warning_identifies_source(
    pi_store: Path,
    tmp_path: Path,
) -> None:
    '''
    Identify the Pi source when evidence inspection loses its file.

    - Regression: a bare I/O error did not identify which dialog's
      evidence was incomplete, making partial coverage ambiguous.
    - Arrange: read native metadata, then prune its session before
      passing that cached record to `observations()`.
    - Proof: evidence stays empty and one warning names the exact ID
      and quoted file path; no replacement source is guessed.

    '''
    path: Path = session(pi_store, tmp_path)
    row: dict = get_dialog('full-dialog-id', 'pi')
    path.unlink()
    warnings: list[str] = []
    evidence: dict[
        tuple[str, str],
        set[str],
    ] = observations([row], warnings)
    assert evidence[('pi', 'full-dialog-id')] == set()
    assert len(warnings) == 1
    assert 'full-dialog-id' in warnings[0]
    assert repr(str(path)) in warnings[0]


def test_pi_launch_runs_resolved_command_directly(
    pi_store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''
    Launch exact Pi resume directly through `resume_main()`.

    - Regression: native resume must not acquire an identity shim or
      require a custom environment payload.
    - Arrange: resolve a named session with a compatible explicit cwd
      so optional WKT lookup cannot spawn Git; capture subprocesses.
    - Proof: exactly one call runs Pi with the resolved ID, pinned
      session directory and cwd, with no shim/environment argument.
    - Proof: the nonzero harness exit status reaches the CLI caller.

    '''
    path: Path = session(pi_store, tmp_path)
    launch: Mock = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr('aiskillz.cli.subprocess.run', launch)
    monkeypatch.setattr(
        'aiskillz.cli.shutil.which', lambda command: '/fixture/pi',
    )
    assert resume_main([
        'Pi work', '--repo', str(tmp_path), '-b', 'pi',
        '--cwd', str(tmp_path),
    ]) == 7
    launch.assert_called_once_with(
        ['pi', '--session', 'full-dialog-id', '--session-dir',
         str(path.parent)],
        cwd=str(tmp_path),
        check=False,
    )
