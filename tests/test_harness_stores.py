# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Fixtures for cross-harness discovery and importable dialog mappings.

'''

from contextlib import closing, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, TextIO
import unittest
from unittest.mock import patch

from aiskillz import name2id, list_dialogs, get_dialog
from aiskillz.cli import main
from aiskillz.dialogs._readers import (
    claude_sessions, opencode_sessions,
)
from aiskillz._xontrib import _load_xontrib_, _unload_xontrib_


class HarnessStoresTests(unittest.TestCase):
    '''
    Verify isolated session fixtures and shell integration.

    '''

    def setUp(self) -> None:
        '''
        Isolate all three harness roots from the user's own sessions.

        '''
        self.temp: tempfile.TemporaryDirectory = (
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(self.temp.cleanup)
        self.root: Path = Path(self.temp.name)
        self.repo: Path = self.root / 'repo'
        self.repo.mkdir()
        self.oc: Path = self.root / 'oc'
        self.oc.mkdir()
        self.claude: Path = self.root / 'claude'
        self.env: Any = patch.dict(
            os.environ,
            {
                'CODEX_HOME': str(self.root / 'absent-codex'),
                'OPENCODE_DATA_DIR': str(self.oc),
                'CLAUDE_CONFIG_DIR': str(self.claude),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_claude_skips_non_object_log_records(self) -> None:
        '''
        Valid JSON scalars and arrays used to crash Claude listing.

        Surround one real metadata event with null, scalar, array,
        and partial JSON records in a temporary log. Discovery must
        still return the real dialog and its cwd/title instead of
        aborting the entire harness store on event.get().

        '''
        folder: Path = self.claude / 'projects/fixture'
        folder.mkdir(parents=True)
        log: Path = folder / 'dialog.jsonl'
        event: dict = {
            'sessionId': 'dialog',
            'cwd': str(self.repo),
            'type': 'custom-title',
            'customTitle': 'Kept title',
        }
        log.write_text(
            '[]\nnull\nfalse\n42\n"scalar"\n'
            + json.dumps(event) + '\n[1]\n{partial',
        )
        rows: list[dict] = list_dialogs(path=None, harness='cld')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'dialog')
        self.assertEqual(rows[0]['name'], 'Kept title')
        self.assertEqual(rows[0]['cwd'], str(self.repo))

    def test_claude_rejects_malformed_identity_title_and_cwd(
        self,
    ) -> None:
        '''
        A truthy list sessionId used to crash public deduplication.

        Write real JSONL events with non-string IDs, titles and cwd,
        followed by valid metadata. Exercise empty and scalar IDs as
        well as unhashable values. Listing must recover valid cwd and
        title while retaining the filename ID until a string ID is
        supplied. A later malformed title must not poison that name.
        This protects name completion's string operations as well as
        dictionary-key construction in `list_dialogs()`.

        '''
        folder: Path = self.claude / 'projects/fixture'
        folder.mkdir(parents=True)
        log: Path = folder / 'fallback-id.jsonl'
        invalid: object
        for invalid in (['bad'], {'bad': 1}, 42, True, None, ''):
            with self.subTest(invalid=invalid):
                bad: dict = {
                    'sessionId': invalid,
                    'cwd': ['wrong-directory'],
                    'type': 'custom-title',
                    'customTitle': ['wrong-title'],
                }
                valid: dict = {
                    'cwd': str(self.repo),
                    'type': 'custom-title',
                    'customTitle': 'Recovered title',
                }
                event: dict
                log.write_text('\n'.join(
                    json.dumps(event) for event in (bad, valid, bad)
                ))
                rows: list[dict] = list_dialogs(
                    path=None, harness='cld',
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['id'], 'fallback-id')
                self.assertEqual(rows[0]['cwd'], str(self.repo))
                self.assertEqual(rows[0]['name'], 'Recovered title')
                valid['sessionId'] = 'verified-id'
                log.write_text('\n'.join(
                    json.dumps(event) for event in (bad, valid)
                ))
                rows = list_dialogs(path=None, harness='cld')
                self.assertEqual(rows[0]['id'], 'verified-id')

    def test_claude_index_validates_fields_before_using_cache(
        self,
    ) -> None:
        '''
        Index entries could publish list titles or use list ID keys.

        Create a newer index containing scalar entries and malformed
        IDs plus one entry for a real log. Ignore invalid identities
        and choose a valid lower-priority title. Then give its cwd a
        wrong type: discovery must read the log for valid metadata
        instead of losing the dialog under exact cwd filtering.

        '''
        folder: Path = self.claude / 'projects/fixture'
        folder.mkdir(parents=True)
        log: Path = folder / 'dialog.jsonl'
        log.write_text(json.dumps({
            'sessionId': 'dialog',
            'cwd': str(self.repo),
            'type': 'custom-title',
            'customTitle': 'From log',
        }) + '\n')
        index: Path = folder / 'sessions-index.json'
        item: dict = {
            'sessionId': 'dialog',
            'projectPath': str(self.repo),
            'customTitle': ['invalid'],
            'aiTitle': {'invalid': True},
            'summary': 'From index',
        }
        index.write_text(json.dumps({'entries': [
            None,
            [],
            {'sessionId': ['invalid']},
            item,
        ]}))
        stamp: float = log.stat().st_mtime + 10
        os.utime(index, (stamp, stamp))
        rows: list[dict] = list_dialogs(path=None, harness='cld')
        self.assertEqual(rows[0]['name'], 'From index')
        self.assertEqual(rows[0]['id'], 'dialog')
        item['projectPath'] = ['invalid']
        index.write_text(json.dumps({'entries': [item]}))
        os.utime(index, (stamp, stamp))
        rows = list_dialogs(path=None, harness='cld')
        self.assertEqual(rows[0]['name'], 'From log')
        self.assertEqual(rows[0]['cwd'], str(self.repo))

    def test_claude_skips_non_object_messages(self) -> None:
        '''
        A user event's non-object `message` used to abort discovery.

        Read a real JSONL log for each malformed nested value.
        Without a valid prompt, discovery must return `(untitled)`.
        Append a valid user message and read again:
        the skipped value must not prevent extracting that prompt.
        These assertions exercise `claude_sessions` through the
        public `list_dialogs` API, including null and scalar values.

        '''
        folder: Path = self.claude / 'projects/fixture'
        folder.mkdir(parents=True)
        log: Path = folder / 'dialog.jsonl'
        message: object
        for message in (None, [], False, 42, 'scalar'):
            with self.subTest(message=message):
                event: dict = {
                    'sessionId': 'dialog',
                    'cwd': str(self.repo),
                    'type': 'user',
                    'message': message,
                }
                malformed: str = json.dumps(event) + '\n'
                log.write_text(malformed)
                rows: list[dict] = list_dialogs(
                    path=None, harness='cld',
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['id'], 'dialog')
                self.assertEqual(rows[0]['name'], '(untitled)')
                event['message'] = {'content': 'Valid prompt'}
                log.write_text(malformed + json.dumps(event))
                rows = list_dialogs(path=None, harness='cld')
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['name'], 'Valid prompt')
                self.assertEqual(rows[0]['cwd'], str(self.repo))

    def test_explicit_harness_lists_require_codex_store(
        self,
    ) -> None:
        '''
        Explicit multi-harness requests silently skipped Codex.

        Point discovery at this fixture's missing Codex database.
        Both canonical and short-key explicit lists must raise even
        alongside another harness. Implicit discovery and `all=True`
        retain their skip behavior; an explicit single selection
        still reports the same error. No real user stores are read.

        '''
        harness: str|list[str]
        for harness in (
            'codex',
            ['codex'],
            ['codex', 'claude'],
            ['cx', 'cld'],
            ['claude', 'cx', 'opencode'],
        ):
            with self.subTest(harness=harness):
                with self.assertRaisesRegex(
                    ValueError, 'Codex session index not found',
                ):
                    list_dialogs(path=None, harness=harness)
        self.assertEqual(list_dialogs(path=None), [])
        self.assertEqual(list_dialogs(
            path=None, harness=['cx', 'cld'], all=True,
        ), [])

    def test_legacy_opencode_archive_opt_in(self) -> None:
        '''
        Manual recording must include pre-SQLite archives too.

        Put an archived session in OpenCode's legacy JSON layout
        without a database. The same include_archived option used
        by --record must return it, while all_sources alone must
        keep it hidden. This prevents backend-dependent behavior.

        '''
        folder: Path = self.oc / 'storage/session/project'
        folder.mkdir(parents=True)
        (folder / 'archived.json').write_text(json.dumps({
            'id': 'old',
            'title': 'Archived dialog',
            'directory': str(self.repo),
            'time': {'updated': 1000, 'archived': 2000},
        }))
        self.assertEqual(list_dialogs(
            path=None, harness='oc', all_sources=True,
        ), [])
        rows: list[dict] = list_dialogs(
            path=None, harness='oc', all_sources=True,
            include_archived=True,
        )
        row: dict
        self.assertEqual([row['id'] for row in rows], ['old'])

    def seed_oc(self) -> None:
        '''
        Create parent, child, archived, and other-directory sessions.

        '''
        connection: sqlite3.Connection
        with closing(
            sqlite3.connect(
                self.oc / 'opencode-stable.db',
            )
        ) as connection:
            connection.execute('''
                CREATE TABLE session (
                    id TEXT, title TEXT, directory TEXT,
                    parent_id TEXT, time_updated INTEGER,
                    time_archived INTEGER
                )
            ''')
            connection.executemany(
                'INSERT INTO session VALUES (?, ?, ?, ?, ?, ?)',
                [
                    (
                        'ses_a',
                        'Shared',
                        str(self.repo),
                        None,
                        5000,
                        None,
                    ),
                    (
                        'ses_b',
                        'Shared',
                        str(self.repo),
                        None,
                        6000,
                        None,
                    ),
                    (
                        'child',
                        'Child',
                        str(self.repo),
                        'ses_a',
                        7000,
                        None,
                    ),
                    ('old', 'Old', str(self.repo), None, 8000, 9000),
                    (
                        'other',
                        'Elsewhere',
                        str(self.root),
                        None,
                        9000,
                        None,
                    ),
                ],
            )
            connection.commit()

    def seed_claude(self, name: str = 'Shared') -> Path:
        '''
        Write a top-level log with cwd and a later explicit rename.

        '''
        folder: Path = (
            self.claude
            / 'projects'
            / re.sub(
                r'[^a-zA-Z0-9]',
                '-',
                str(self.repo),
            )
        )
        folder.mkdir(parents=True, exist_ok=True)
        path: Path = folder / 'claude-id.jsonl'
        events: list[dict] = [
            {
                'type': 'user',
                'cwd': str(self.repo),
                'sessionId': 'claude-id',
                'message': {'content': 'First prompt'},
            },
            {
                'type': 'custom-title',
                'customTitle': name,
                'sessionId': 'claude-id',
            },
        ]
        e: dict
        path.write_text(
            '\n'.join(json.dumps(e) for e in events) + '\n'
        )
        return path

    def test_oc_scope_parent_filter_and_legacy_json(self) -> None:
        '''
        OpenCode uses non-UUID IDs and two storage generations.

        Both readers must preserve IDs, scope by directory, and hide
        archived sessions without treating child sessions as parents.

        '''
        self.seed_oc()
        before: bytes = (self.oc / 'opencode-stable.db').read_bytes()
        rows: list[dict] = opencode_sessions(self.oc, str(self.repo))
        r: dict
        self.assertEqual({r['id'] for r in rows}, {'ses_a', 'ses_b'})
        self.assertEqual(
            before,
            (self.oc / 'opencode-stable.db').read_bytes(),
        )
        legacy: Path = self.root / 'legacy/storage/session/project'
        legacy.mkdir(parents=True)
        (legacy / 'ses_l.json').write_text(
            json.dumps(
                {
                    'id': 'ses_l',
                    'title': 'Legacy',
                    'directory': str(self.repo),
                    'time': {'updated': 5000},
                }
            )
        )
        rows = opencode_sessions(
            self.root / 'legacy', str(self.repo)
        )
        self.assertEqual(rows[0]['id'], 'ses_l')

    def test_oc_skips_non_object_legacy_records(self) -> None:
        '''
        Valid JSON scalars and arrays crashed legacy OpenCode reads.

        Seed real session files alongside null, boolean, numeric,
        string and array JSON values. Public discovery must skip
        these non-record values and preserve the valid dialog, both
        with and without cwd filtering. Snapshot the files to prove
        that recovering discovery leaves harness metadata untouched.

        '''
        folder: Path = self.oc / 'storage/session/project'
        folder.mkdir(parents=True)
        values: list[object] = [
            None,
            False,
            42,
            'scalar',
            [],
            [1],
            {
                'id': 'ses_kept',
                'title': 'Kept dialog',
                'directory': str(self.repo),
                'time': {'updated': 5000},
            },
        ]
        ordinal: int
        value: object
        for ordinal, value in enumerate(values):
            (folder / f'{ordinal}.json').write_text(
                json.dumps(value),
            )
        path: Path
        before: dict[Path, bytes] = {
            path: path.read_bytes() for path in folder.glob('*.json')
        }
        scope: str|None
        for scope in (None, str(self.repo)):
            with self.subTest(scope=scope):
                rows: list[dict] = list_dialogs(
                    path=scope, harness='oc',
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['id'], 'ses_kept')
                self.assertEqual(rows[0]['name'], 'Kept dialog')
                self.assertEqual(rows[0]['cwd'], str(self.repo))
        self.assertEqual(before, {
            path: path.read_bytes() for path in before
        })

    def test_oc_skips_malformed_legacy_fields(self) -> None:
        '''
        Object-shaped legacy records still crashed public discovery.

        A scalar or null `time` failed mapping access; a missing or
        unhashable ID failed dictionary insertion. A non-numeric
        update time failed timestamp conversion. Missing directories
        raised KeyError on unscoped discovery; non-string directories
        became invalid public metadata. Place each malformed variant
        beside a valid dialog in real JSON files.
        Scoped and unscoped reads, including archive opt-in, must
        retain only the valid dialog and leave every file unchanged.

        '''
        folder: Path = self.oc / 'storage/session/project'
        folder.mkdir(parents=True)
        good: dict = {
            'id': 'ses_kept',
            'title': 'Kept dialog',
            'directory': str(self.repo),
            'time': {'updated': 5000},
        }
        malformed: list[dict] = []
        value: object
        for value in (None, False, 42, 'scalar', [], [1]):
            malformed.append({**good, 'time': value})
        for value in (None, False, 42, '', [], {}):
            malformed.append({**good, 'id': value})
        without_id: dict = dict(good)
        del without_id['id']
        malformed.append(without_id)
        for value in (None, False, 42, '', [], {}):
            malformed.append({**good, 'directory': value})
        without_directory: dict = dict(good)
        del without_directory['directory']
        malformed.append(without_directory)
        for value in (None, False, '5000', [], {}):
            malformed.append({
                **good,
                'time': {'updated': value},
            })
        ordinal: int
        record: dict
        for ordinal, record in enumerate([good, *malformed]):
            (folder / f'{ordinal}.json').write_text(
                json.dumps(record),
            )
        path: Path
        before: dict[Path, bytes] = {
            path: path.read_bytes() for path in folder.glob('*.json')
        }
        scope: str|None
        for scope in (None, str(self.repo)):
            include_archived: bool
            for include_archived in (False, True):
                with self.subTest(
                    scope=scope, include_archived=include_archived,
                ):
                    rows: list[dict] = list_dialogs(
                        path=scope,
                        harness='oc',
                        include_archived=include_archived,
                    )
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['id'], 'ses_kept')
                    self.assertEqual(rows[0]['updated_at'], 5)
        self.assertEqual(before, {
            path: path.read_bytes() for path in before
        })

    def test_claude_rename_partial_tail_and_cwd_collision(
        self,
    ) -> None:
        '''
        Claude project directory encoding is lossy, and logs grow
        live.

        Read the latest explicit title despite a partial trailing
        JSON record, then reject a mismatching cwd even in the same
        folder.

        '''
        path: Path = self.seed_claude('Renamed')
        stream: TextIO
        with path.open('a') as stream:
            stream.write('{"type":')
        rows: list[dict] = claude_sessions(
            self.claude,
            str(self.repo),
        )
        self.assertEqual(rows[0]['name'], 'Renamed')
        self.assertEqual(rows[0]['id'], 'claude-id')
        path.write_text(
            json.dumps(
                {
                    'type': 'user',
                    'cwd': str(self.root),
                    'sessionId': 'wrong',
                    'message': {'content': 'Other'},
                }
            )
        )
        self.assertEqual(
            claude_sessions(
                self.claude,
                str(self.repo),
            ),
            [],
        )

    def test_claude_fresh_index_and_stale_rename(self) -> None:
        '''
        A stale Claude index must not hide a newer session rename.

        Fresh indexes provide names quickly; a later log update must
        invalidate that fast path and recover the name from the log.

        '''
        path: Path = self.seed_claude('New name')
        index: Path = path.parent / 'sessions-index.json'
        index.write_text(
            json.dumps(
                {
                    'entries': [
                        {
                            'sessionId': 'claude-id',
                            'projectPath': str(self.repo),
                            'summary': 'Indexed name',
                        }
                    ]
                }
            )
        )
        os.utime(index, (path.stat().st_mtime + 10,) * 2)
        self.assertEqual(
            claude_sessions(
                self.claude,
                str(self.repo),
            )[0]['name'],
            'Indexed name',
        )
        os.utime(index, (0, 0))
        self.assertEqual(
            claude_sessions(
                self.claude,
                str(self.repo),
            )[0]['name'],
            'New name',
        )

    def test_claude_ai_title_and_last_prompt(self) -> None:
        '''
        AI titles and last-prompt metadata were ignored by discovery.

        Append an AI title after an explicit rename to reproduce the
        naming sequence recognized by ai.reply. Then replace the log
        with two last-prompt records and verify the newest wins. Both
        cases retain the original cwd and resumable dialog ID.

        '''
        path: Path = self.seed_claude('Earlier custom title')
        stream: TextIO
        with path.open('a') as stream:
            stream.write(json.dumps({
                'type': 'ai-title',
                'aiTitle': 'Latest AI title',
            }) + '\n')
        rows: list[dict] = claude_sessions(
            self.claude, str(self.repo),
        )
        self.assertEqual(rows[0]['name'], 'Latest AI title')
        events: list[dict] = [
            {'cwd': str(self.repo), 'sessionId': 'claude-id'},
            {'type': 'last-prompt', 'lastPrompt': 'Old prompt'},
            {'type': 'last-prompt', 'lastPrompt': 'New prompt'},
        ]
        event: dict
        path.write_text('\n'.join(
            json.dumps(event) for event in events
        ))
        rows = claude_sessions(self.claude, str(self.repo))
        self.assertEqual(rows[0]['name'], 'New prompt')
        self.assertEqual(rows[0]['id'], 'claude-id')

    def test_defaults_select_all_harnesses_at_cwd(self) -> None:
        '''
        Bare ai.dlogs previously hid every harness except Codex.

        Seed OpenCode and Claude, with other-cwd and child OpenCode
        records, and make os.getcwd return the fixture repository.
        Default Python and CLI calls must include both harnesses,
        exclude other scopes and children, and retain explicit
        single-harness filtering. All roots are isolated by setUp.

        '''
        self.seed_oc()
        self.seed_claude()
        with patch('os.getcwd', return_value=str(self.repo)):
            names: dict[str, str] = name2id()
            self.assertEqual(
                set(names.values()),
                {'ses_a', 'ses_b', 'claude-id'},
            )
            output: StringIO = StringIO()
            with redirect_stdout(output):
                status: int = main(['--json'])
            self.assertEqual(status, 0)
            rows: list[dict] = json.loads(output.getvalue())
            row: dict
            self.assertEqual(
                {row['id'] for row in rows},
                {'ses_a', 'ses_b', 'claude-id'},
            )
            self.assertEqual(
                name2id(harness='claude'), {'Shared': 'claude-id'},
            )

    def test_get_dialog_by_id_and_ambiguity(self) -> None:
        '''
        ID-only consumers need metadata without choosing a cwd.

        Seed both stores and find a dialog saved outside this repo.
        Check full metadata, alias filtering and missing-ID behavior.
        Duplicate an ID across harnesses through mocked metadata and
        require an ambiguity error rather than silently picking one.

        '''
        self.seed_oc()
        self.seed_claude()
        dialog: dict|None = get_dialog('other')
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog['harness'], 'opencode')
        self.assertEqual(dialog['cwd'], str(self.root))
        self.assertEqual(get_dialog('ses_a', harness='oc')['id'],
                         'ses_a')
        self.assertIsNone(get_dialog('missing'))
        self.assertIsNone(get_dialog('ses_a', harness='cld'))
        with patch(
            'aiskillz.dialogs._api.list_dialogs',
            return_value=[
                {'harness': 'codex', 'id': 'shared'},
                {'harness': 'claude', 'id': 'shared'},
            ],
        ):
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                get_dialog('shared')

        with self.assertRaisesRegex(ValueError, 'nonempty'):
            get_dialog('')

    def test_mapping_duplicates_and_all_override(self) -> None:
        '''
        Duplicate names must never overwrite IDs in the public
        mapping.

        all=True must ignore both supplied filters and expose records
        from other scopes and harnesses, skipping absent stores.

        '''
        self.seed_oc()
        self.seed_claude()
        mapping: dict[str, str] = name2id(
            self.repo,
            harness=['oc', 'claude'],
        )
        self.assertEqual(
            set(mapping.values()),
            {
                'ses_a',
                'ses_b',
                'claude-id',
            },
        )
        self.assertEqual(len(mapping), 3)
        rows: list[dict] = list_dialogs(
            '/deliberately/wrong',
            harness='claude',
            all=True,
        )
        r: dict
        self.assertEqual(
            {r['id'] for r in rows},
            {
                'ses_a',
                'ses_b',
                'child',
                'other',
                'claude-id',
            },
        )
        with self.assertRaisesRegex(ValueError, 'Unknown harness'):
            name2id(harness='invalid')

    def test_callable_alias_streams_and_status(self) -> None:
        '''
        The packaged alias previously launched a Python subprocess.

        Invoke the actual callable with help and invalid arguments
        using separate capture streams. Both argparse exits must
        become shell statuses, leaving the host process and global
        streams intact. Mocked discovery proves normal JSON output
        uses the supplied stream without accessing real stores.
        A shell-only store override must reach Python readers and
        leave the process environment unchanged after the call.

        '''
        from types import SimpleNamespace
        import sys

        xsh: Any = SimpleNamespace(aliases={}, ctx={})
        _load_xontrib_(xsh)
        alias: Any = xsh.aliases['ai.dlogs']
        self.assertTrue(callable(alias))
        self.assertFalse(alias.__xonsh_threadable__)
        self.assertEqual(
            xsh.aliases['ai.resume'],
            [
                sys.executable,
                '-m',
                'aiskillz',
                'resume',
            ],
        )
        out: StringIO = StringIO()
        err: StringIO = StringIO()
        original: TextIO = sys.stdout
        self.assertEqual(alias(
            ['--help'], stdout=out, stderr=err,
        ), 0)
        self.assertIn('usage:', out.getvalue())
        self.assertEqual(alias(
            ['--unknown-option'], stdout=out, stderr=err,
        ), 2)
        self.assertIn('error:', err.getvalue())
        out = StringIO()
        with patch(
            'aiskillz.cli.dialogs.list_dialogs', return_value=[],
        ):
            self.assertEqual(alias(
                ['--json'], stdout=out, stderr=err,
            ), 0)
        self.assertEqual(json.loads(out.getvalue()), [])
        self.assertIs(sys.stdout, original)
        from xonsh.built_ins import XSH

        previous_env: dict[str, str] = dict(os.environ)
        shell_env: Any = SimpleNamespace(detype=lambda: {
            'CODEX_HOME': '/synthetic/xonsh/store',
        })

        def check_environment(args: list[str]) -> int:
            '''
            Inspect the environment seen by the CLI dispatcher.

            '''
            self.assertEqual(
                os.environ['CODEX_HOME'], '/synthetic/xonsh/store',
            )
            return 0

        with (
            patch.object(XSH, 'env', shell_env),
            patch('aiskillz.cli.main', check_environment),
        ):
            self.assertEqual(alias([], stdout=out, stderr=err), 0)
        self.assertEqual(dict(os.environ), previous_env)
        _unload_xontrib_(xsh)

    def test_xontrib_reloads_preserve_prior_aliases(self) -> None:
        '''
        Repeated loads used to save extension aliases as originals.

        Load twice with existing user bindings, then unload: both
        prior bindings must return. Repeat with no original aliases
        to require their removal. If a user changes either binding
        between loads, the latest user binding must survive unload;
        changes made after the final load must also remain intact.
        Exercise the actual loader and unloader with isolated shell
        aliases and context, without launching a harness process.

        '''
        from types import SimpleNamespace

        original: dict
        for original in (
            {},
            {
                'ai.dlogs': ['old-dlogs'],
                'ai.resume': ['old-resume'],
            },
        ):
            with self.subTest(original=original):
                xsh: SimpleNamespace = SimpleNamespace(
                    aliases=dict(original), ctx={},
                )
                _load_xontrib_(xsh)
                _load_xontrib_(xsh)
                _unload_xontrib_(xsh)
                self.assertEqual(xsh.aliases, original)
                self.assertEqual(xsh.ctx, {})

        xsh = SimpleNamespace(aliases={}, ctx={})
        _load_xontrib_(xsh)
        replacement: dict = {
            'ai.dlogs': ['replacement-dlogs'],
            'ai.resume': ['replacement-resume'],
        }
        xsh.aliases.update(replacement)
        _load_xontrib_(xsh)
        _load_xontrib_(xsh)
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases, replacement)
        _load_xontrib_(xsh)
        _load_xontrib_(xsh)
        xsh.aliases.update(replacement)
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases, replacement)

    def test_xontrib_unload_restores_alias(self) -> None:
        '''
        Loading an extension must not permanently erase a user's
        alias.

        Restore the previous alias on unload, but preserve a later
        replacement made by the user while the extension was loaded.

        '''
        from types import SimpleNamespace

        xsh: SimpleNamespace = SimpleNamespace(
            aliases={
                'ai.dlogs': ['old'],
                'ai.resume': ['old-resume'],
            },
            ctx={},
        )
        _load_xontrib_(xsh)
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases['ai.dlogs'], ['old'])
        self.assertEqual(
            xsh.aliases['ai.resume'], ['old-resume'],
        )
        _load_xontrib_(xsh)
        xsh.aliases['ai.dlogs'] = ['new']
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases['ai.dlogs'], ['new'])


if __name__ == '__main__':
    unittest.main()
