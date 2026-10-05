# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise offline session discovery and the sourceable Xonsh alias.

'''

from contextlib import closing
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from importlib.metadata import entry_points
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aiskillz.dialogs._readers import codex_sessions
from aiskillz.cli import format_dialog_table as table
from aiskillz.cli import main as dlogs_main
from aiskillz.wkt import WktLookup


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

    def test_malformed_relation_reports_cli_error(self) -> None:
        '''
        WKT formatting errors used to bypass main()'s error handler.

        Use the real Codex reader and Git lookup with malformed
        relations.json in a temporary repo. The CLI must exit one
        with its normal diagnostic, leaving the relation untouched.
        JSON output bypasses WKT formatting and remains usable.

        '''
        subprocess.run(
            [
                'git',
                'init',
                '--quiet',
                str(self.repo),
            ],
            check=True, capture_output=True,
        )
        relations: Path = (
            self.repo / '.ai/state/dialogs/relations.json'
        )
        relations.parent.mkdir(parents=True)
        relations.write_text('{invalid')
        error: io.StringIO = io.StringIO()
        with (
            patch.dict(os.environ, {'CODEX_HOME': str(self.home)}),
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            dlogs_main([
                str(self.repo),
                '-b',
                'cx',
            ])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn('ai.dlogs:', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())
        self.assertEqual(relations.read_text(), '{invalid')
        with (
            patch.dict(os.environ, {'CODEX_HOME': str(self.home)}),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(dlogs_main([
                str(self.repo),
                '-b',
                'cx',
                '--json',
            ]), 0)

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

    def test_ids_are_opt_in_and_controls_removed(self) -> None:
        '''
        The default table no longer needs wide dialog IDs.

        A session title can contain terminal controls. Keep one
        logical row, show the full ID with `--did`, and retain the
        unchanged ID in JSON for callers that need it.

        '''
        uuid: str = '01980000-0000-7000-8000-000000000001'
        sessions: list[dict] = [{
            'harness': 'codex',
            'id': uuid,
            'name': 'name\nwith\x1b[31m controls',
        }]
        output: str = table(sessions)
        self.assertNotIn(uuid, output)
        self.assertNotIn('DIALOG ID', output)
        self.assertNotIn('\x1b', output)
        self.assertEqual(
            output.splitlines()[0],
            'sort-by: "last-update-time" (newest first)',
        )
        self.assertEqual(output.splitlines()[1], 'HARNESS=codex')
        self.assertEqual(len(output.splitlines()), 5)
        self.assertIn(uuid, table(sessions, show_did=True))
        self.assertIn('DIALOG ID', table([], show_did=True))

        with patch(
            'aiskillz.cli.dialogs.list_dialogs',
            return_value=sessions,
        ):
            rendered: io.StringIO = io.StringIO()
            with redirect_stdout(rendered):
                self.assertEqual(dlogs_main(['--did']), 0)
            self.assertIn(uuid, rendered.getvalue())
            rendered = io.StringIO()
            with redirect_stdout(rendered):
                self.assertEqual(dlogs_main([
                    '--did',
                    '--json',
                ]), 0)
            self.assertEqual(
                json.loads(rendered.getvalue()), sessions,
            )

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
            [
                'git',
                'init',
                '--quiet',
                str(self.repo),
            ],
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
        self.assertEqual(
            WktLookup().roots(str(nested)), {str(linked)},
        )
        self.assertEqual(
            WktLookup().roots(str(self.repo)), set(),
        )
        self.assertEqual(
            WktLookup().roots(str(self.home)), set(),
        )
        self.assertEqual(
            WktLookup().roots(str(linked / 'gone')), set(),
        )
        self.assertEqual(WktLookup().roots(''), set())

    def test_table_caps_names_and_orders_columns(self) -> None:
        '''
        Long session names previously pushed cwd far off screen.

        Render a long name alongside an exact-boundary name. Check
        ellipsis truncation and harness/name/WKT order, then
        stable ID alignment when requested. Preserve the original
        name in the caller's records.
        The shared cwd moves above the header instead of repeating.

        '''
        name: str = 'long' * 40
        sessions: list[dict] = [
            {
                'name': name,
                'id': 'dialog-one',
                'cwd': '/repo',
                'harness': 'claude',
            },
            {
                'name': 'x' * 36,
                'id': 'dialog-two',
                'cwd': '/repo',
                'harness': 'codex',
            },
        ]
        lines: list[str] = table(sessions).splitlines()
        self.assertEqual(
            lines[0], 'sort-by: "last-update-time" (newest first)',
        )
        self.assertEqual(lines[1], 'CWD=/repo')
        self.assertEqual(lines[2], '')
        self.assertEqual(
            lines[3].split(),
            ['HARNESS', 'NAME', 'WKT'],
        )
        self.assertTrue(lines[4].startswith('claude   '))
        self.assertTrue(lines[5].startswith('codex    '))
        self.assertIn(name[:35] + '…', lines[4])
        self.assertIn('x' * 36, lines[5])
        self.assertNotIn('dialog-one', lines[4])
        with_ids: list[str] = table(
            sessions, show_did=True,
        ).splitlines()
        self.assertEqual(
            with_ids[3].split(),
            ['HARNESS', 'NAME', 'WKT', 'DIALOG', 'ID'],
        )
        self.assertEqual(with_ids[4].index('dialog-one'), 52)
        self.assertEqual(with_ids[5].index('dialog-two'), 52)
        self.assertEqual(sessions[0]['name'], name)

    def test_uniform_harness_moves_above_table(self) -> None:
        '''
        A single-harness filter used to repeat its value per row.

        Render two dialogs from the same harness and cwd, then a
        mixed-cwd pair. Only uniform values move into context lines;
        the remaining CWD column still distinguishes mixed paths.

        '''
        rows: list[dict] = [
            {
                'name': 'One',
                'id': 'one',
                'cwd': '/repo',
                'harness': 'codex',
            },
            {
                'name': 'Two',
                'id': 'two',
                'cwd': '/repo',
                'harness': 'codex',
            },
        ]
        output: str = table(rows)
        self.assertTrue(output.startswith(
            'sort-by: "last-update-time" (newest first)\n'
            'CWD=/repo\nHARNESS=codex\n\nNAME',
        ))
        self.assertNotIn('HARNESS', output.splitlines()[4])
        rows[1]['cwd'] = '/other'
        mixed: str = table(rows)
        self.assertTrue(mixed.startswith(
            'sort-by: "last-update-time" (newest first)\n'
            'HARNESS=codex\n\nNAME',
        ))
        self.assertIn('CWD', mixed.splitlines()[3])

    def test_short_harness_flag_leaves_help_at_h(self) -> None:
        '''
        `-h` previously selected a harness instead of showing help.

        Check the default argparse help and ensure `-b cx` still
        selects Codex before dialog discovery runs.

        '''
        output: io.StringIO = io.StringIO()
        with redirect_stdout(output):
            with self.assertRaises(SystemExit) as exit_info:
                dlogs_main(['-h'])
        self.assertEqual(exit_info.exception.code, 0)
        self.assertIn('-b', output.getvalue())
        with patch('aiskillz.cli.dialogs.list_dialogs') as listing:
            listing.return_value = []
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dlogs_main([
                    '-b',
                    'cx',
                ]), 0)
        self.assertEqual(listing.call_args.args[1], 'cx')

    def test_terminal_color_stays_on_table_header(self) -> None:
        '''
        Context lines precede the terminal table header.

        Simulate a TTY with one filtered dialog. The context must
        remain plain text and the grey escape must wrap the actual
        column header, not the first context line.

        '''
        class Terminal(io.StringIO):
            '''
            Capture output while reporting TTY capability.

            '''

            def isatty(self) -> bool:
                '''
                Enable the CLI's terminal color branch.

                '''
                return True

        output: Terminal = Terminal()
        rows: list[dict] = [{
            'name': 'One',
            'id': 'one',
            'cwd': '/repo',
            'harness': 'codex',
        }]
        with (
            patch('aiskillz.cli.dialogs.list_dialogs',
                  return_value=rows),
            patch('aiskillz.cli.sys.stdout', output),
            patch.dict(os.environ, {'TERM': 'xterm'}),
        ):
            os.environ.pop('NO_COLOR', None)
            self.assertEqual(dlogs_main([]), 0)

        self.assertTrue(output.getvalue().startswith(
            '\x1b[90msort-by: \x1b[0m'
            '"last-update-time" (newest first)\n'
            '\x1b[90mCWD=\x1b[0m/repo\n'
            '\x1b[90mHARNESS=\x1b[0mcodex\n\n'
            '\x1b[90mNAME',
        ))

    @unittest.skipUnless(shutil.which('xonsh'), 'xonsh unavailable')
    def test_installed_xontrib_from_other_directory(self) -> None:
        '''
        A successful pip install must expose the Xontrib outside cwd.

        Source-based tests bypass namespace-package discovery and can
        hide broken packaging. Start a fresh Xonsh in the disposable
        repository with no PYTHONPATH or rc files, load the installed
        extension, and invoke its CLI against the fixture. Skip only
        when this interpreter has no installed aiskillz entry point.

        '''
        installed: bool = bool(entry_points(
            group='xonsh.xontribs', name='aiskillz',
        ))
        if not installed:
            self.skipTest('aiskillz distribution not installed')
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
                sys.executable,
                '-m',
                'xonsh',
                '--no-rc',
                '-c',
                'xontrib load aiskillz; '
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
            [
                'xonsh',
                '--no-rc',
                '-c',
                command,
            ],
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
