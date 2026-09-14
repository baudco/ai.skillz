# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise offline session discovery and the sourceable Xonsh alias.

'''

from contextlib import closing
import json
from importlib.metadata import entry_points
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from pyskillz._stores import codex_sessions
from pyskillz._dlogs import table, _worktree_name


ROOT: Path = Path(__file__).resolve().parents[1]


class DlogsTests(unittest.TestCase):
    '''
    Verify isolated session fixtures and shell integration.

    '''

    def setUp(self) -> None:
        '''
        Seed an independent Codex index with multiple session kinds.

        '''
        self.temporary: tempfile.TemporaryDirectory = (
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(self.temporary.cleanup)
        self.home: Path = Path(self.temporary.name)
        self.repo: Path = self.home / "repo with ' spaces"
        self.repo.mkdir()
        self.database: Path = self.home / 'state_5.sqlite'
        connection: sqlite3.Connection
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute('''
                CREATE TABLE threads (
                    id TEXT, name TEXT, title TEXT, cwd TEXT,
                    source TEXT, updated_at INTEGER, archived INTEGER
                )
            ''')
            connection.executemany(
                'INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    (
                        'one',
                        'Renamed',
                        'Old title',
                        str(self.repo),
                        'cli',
                        10,
                        0,
                    ),
                    (
                        'two',
                        '',
                        'Editor task',
                        str(self.repo),
                        'vscode',
                        20,
                        0,
                    ),
                    (
                        'child',
                        None,
                        'Subagent',
                        str(self.repo),
                        'subAgent',
                        30,
                        0,
                    ),
                    (
                        'archived',
                        None,
                        'Archived',
                        str(self.repo),
                        'cli',
                        40,
                        1,
                    ),
                    (
                        'elsewhere',
                        None,
                        'Other repo',
                        str(self.home),
                        'cli',
                        50,
                        0,
                    ),
                ],
            )
            connection.commit()

    def test_scope_names_order_and_read_only(self) -> None:
        '''
        A launcher must not mix other cwd values or archived IDs.

        Renamed sessions should use their current name, while blank
        names fall back to titles. Listing must preserve DB bytes.

        '''
        before: bytes = self.database.read_bytes()
        rows: list[dict] = codex_sessions(self.home, str(self.repo))
        row: dict
        self.assertEqual([row['id'] for row in rows], ['two', 'one'])
        self.assertEqual(rows[1]['name'], 'Renamed')
        self.assertEqual(rows[0]['name'], 'Editor task')
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(len(codex_sessions(self.home, None)), 3)
        self.assertEqual(
            len(
                codex_sessions(
                    self.home,
                    str(self.repo),
                    all_sources=True,
                )
            ),
            3,
        )

    def test_old_schema_and_missing_database(self) -> None:
        '''
        Older indexes lack names; missing indexes must stay absent.

        This prevents both an SQL error on a known older layout and
        accidental creation of a misleading empty Codex database.

        '''
        connection: sqlite3.Connection
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                'ALTER TABLE threads DROP COLUMN name',
            )
            connection.commit()
        rows: list[dict] = codex_sessions(self.home, str(self.repo))
        self.assertEqual(rows[1]['name'], 'Old title')
        missing: Path = self.home / 'absent'
        with self.assertRaisesRegex(ValueError, 'not found'):
            codex_sessions(missing, None)
        self.assertFalse(missing.exists())

    def test_table_preserves_ids_and_removes_controls(self) -> None:
        '''
        Session titles can contain newlines and terminal escapes.

        Rendering must keep each session on one logical line and
        preserve the complete ID for resume and selection tools.

        '''
        uuid: str = '01980000-0000-7000-8000-000000000001'
        output: str = table(
            [
                {
                    'harness': 'codex',
                    'id': uuid,
                    'name': 'name\nwith\x1b[31m controls',
                }
            ]
        )
        self.assertIn(uuid, output)
        self.assertNotIn('\x1b', output)
        self.assertEqual(len(output.splitlines()), 2)
        self.assertIn('DIALOG ID', table([]))

    @unittest.skipUnless(shutil.which('git'), 'git unavailable')
    def test_worktree_from_recorded_subdirectory(self) -> None:
        '''
        A cwd basename cannot identify its owning linked worktree.

        Build Git's linked-worktree metadata in a disposable repo,
        without commits, and query a nested cwd. Git must return the
        worktree root name, while main, missing, and non-Git paths
        remain blank. No session-owned metadata is modified.

        '''
        subprocess.run(
            ['git', 'init', '--quiet', str(self.repo)],
            check=True, capture_output=True,
        )
        linked: Path = self.home / 'feature'
        nested: Path = linked / 'src'
        nested.mkdir(parents=True)
        metadata: Path = self.repo / '.git/worktrees/feature'
        metadata.mkdir(parents=True)
        (metadata / 'HEAD').write_text('ref: refs/heads/feature\n')
        (metadata / 'commondir').write_text('../..\n')
        gitfile: Path = linked / '.git'
        (metadata / 'gitdir').write_text(str(gitfile) + '\n')
        gitfile.write_text(f'gitdir: {metadata}\n')
        self.assertEqual(_worktree_name(str(nested)), 'feature')
        self.assertEqual(_worktree_name(str(self.repo)), '')
        self.assertEqual(_worktree_name(str(self.home)), '')
        self.assertEqual(_worktree_name(str(linked / 'gone')), '')
        self.assertEqual(_worktree_name(''), '')

    def test_table_caps_names_and_orders_columns(self) -> None:
        '''
        Long session names previously pushed cwd far off screen.

        Render a long name alongside an exact-boundary name. Check
        ellipsis truncation, stable ID alignment, and name/ID/cwd/
        harness order, while preserving the caller's original name.

        '''
        name: str = 'long' * 40
        sessions: list[dict] = [
            {
                'name': name, 'id': 'dialog-one',
                'cwd': '/repo', 'harness': 'claude',
            },
            {
                'name': 'x' * 36, 'id': 'dialog-two',
                'cwd': '/repo', 'harness': 'codex',
            },
        ]
        lines: list[str] = table(sessions).splitlines()
        self.assertEqual(
            lines[0].split(),
            [
                'NAME', 'DIALOG', 'ID', 'UPDATED', '(UTC)',
                'CWD', 'WKT', 'HARNESS',
            ],
        )
        self.assertTrue(lines[1].startswith(name[:35] + '…'))
        self.assertTrue(lines[2].startswith('x' * 36))
        self.assertEqual(lines[1].index('dialog-one'), 38)
        self.assertEqual(lines[2].index('dialog-two'), 38)
        self.assertEqual(sessions[0]['name'], name)

    @unittest.skipUnless(shutil.which('xonsh'), 'xonsh unavailable')
    def test_installed_xontrib_from_other_directory(self) -> None:
        '''
        A successful pip install must expose the Xontrib outside cwd.

        Source-based tests bypass namespace-package discovery and can
        hide broken packaging. Start a fresh Xonsh in the disposable
        repository with no PYTHONPATH or rc files, load the installed
        extension, and invoke its CLI against the fixture. Skip only
        when this interpreter has no installed pyskillz entry point.

        '''
        installed: bool = bool(entry_points(
            group='xonsh.xontribs', name='pyskillz',
        ))
        if not installed:
            self.skipTest('pyskillz distribution not installed')
        import sys

        env: dict[str, str] = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.update({
            'CODEX_HOME': str(self.home),
            'HOME': str(self.home),
            'XONSH_DATA_DIR': str(self.home / 'xonsh-data'),
            'XONSH_CACHE_DIR': str(self.home / 'xonsh-cache'),
        })
        result: subprocess.CompletedProcess = subprocess.run(
            [
                sys.executable, '-m', 'xonsh', '--no-rc', '-c',
                'xontrib load pyskillz; '
                'ai.dlogs --harness codex --json',
            ],
            cwd=self.repo, env=env, capture_output=True,
            text=True, check=True,
        )
        rows: list[dict] = json.loads(result.stdout)
        row: dict
        self.assertEqual([row['id'] for row in rows], ['two', 'one'])

    @unittest.skipUnless(shutil.which('xonsh'), 'xonsh unavailable')
    def test_alias_uses_invocation_cwd_and_env(self) -> None:
        '''
        A sourced alias must work outside its source checkout.

        Source twice, then invoke from a cwd with spaces and a quote;
        CODEX_HOME must select the fixture, never the user's index.

        '''
        source: str = str(ROOT / 'aliases.xsh')
        command: str = (
            f'source {source!r}\nsource {source!r}\n'
            'ai.dlogs --harness codex --json'
        )
        result: subprocess.CompletedProcess = subprocess.run(
            ['xonsh', '--no-rc', '-c', command],
            cwd=self.repo,
            env=os.environ
            | {
                'CODEX_HOME': str(self.home),
                'HOME': str(self.home),
                'XONSH_DATA_DIR': str(self.home / 'xonsh-data'),
                'XONSH_CACHE_DIR': str(self.home / 'xonsh-cache'),
            },
            capture_output=True,
            text=True,
            check=True,
        )
        rows: list[dict] = json.loads(result.stdout)
        row: dict
        self.assertEqual([row['id'] for row in rows], ['two', 'one'])


if __name__ == '__main__':
    unittest.main()
