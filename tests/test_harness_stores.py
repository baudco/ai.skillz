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

from pyskillz import name2id, list_dialogs, get_dialog
from pyskillz._dlogs import main
from pyskillz._stores import claude_sessions, opencode_sessions
from pyskillz._xontrib import _load_xontrib_, _unload_xontrib_


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
                'type': 'ai-title', 'aiTitle': 'Latest AI title',
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
        with patch('pyskillz._dlogs.list_dialogs', return_value=[
            {'harness': 'codex', 'id': 'shared'},
            {'harness': 'claude', 'id': 'shared'},
        ]):
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

    def test_xontrib_unload_restores_alias(self) -> None:
        '''
        Loading an extension must not permanently erase a user's
        alias.

        Restore the previous alias on unload, but preserve a later
        replacement made by the user while the extension was loaded.

        '''
        from types import SimpleNamespace

        xsh: SimpleNamespace = SimpleNamespace(
            aliases={'ai.dlogs': ['old']}, ctx={},
        )
        _load_xontrib_(xsh)
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases['ai.dlogs'], ['old'])
        _load_xontrib_(xsh)
        xsh.aliases['ai.dlogs'] = ['new']
        _unload_xontrib_(xsh)
        self.assertEqual(xsh.aliases['ai.dlogs'], ['new'])


if __name__ == '__main__':
    unittest.main()
