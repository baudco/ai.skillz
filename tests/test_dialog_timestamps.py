# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.


'''
Verify optional UTC recency without changing metadata or sorting.

`list_dialogs()` already orders full timestamps; these tests exercise
its handoff to `table()` using synthetic metadata and a disposable
Git repository. No harness database or assignment store is modified.

'''

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aiskillz.cli import format_dialog_table as table
from aiskillz.cli import main as dlogs_main
from aiskillz import list_dialogs


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class DialogTimestampTests(unittest.TestCase):
    '''
    Check opt-in timestamps using isolated dialog records.

    '''

    def setUp(self) -> None:
        '''
        Prepare a main checkout outside every real harness store.

        '''
        self.temp: tempfile.TemporaryDirectory = (
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(self.temp.cleanup)
        self.root: Path = Path(self.temp.name) / 'main'
        subprocess.run(
            ['git', 'init', '--quiet', str(self.root)],
            capture_output=True, check=True,
        )


    def test_updated_time_display_and_order(self) -> None:
        '''
        Feed reversed store records through list_dialogs, then render
        known Unix times. The newest must come first even when the
        timestamp column is hidden. Opting in shows UTC minutes;
        original fractional values stay untouched. Missing times
        in caller-provided rows render blank.

        '''
        records: list[dict] = [
            {
                'name': 'old', 'id': 'one', 'cwd': str(self.root),
                'harness': 'claude', 'updated_at': 0.0,
            },
            {
                'name': 'new', 'id': 'two', 'cwd': str(self.root),
                'harness': 'claude', 'updated_at': 60.5,
            },
        ]
        with patch(
            'aiskillz.dialogs._api.claude_sessions',
            return_value=records,
        ):
            rows: list[dict] = list_dialogs(harness='claude')
        self.assertEqual(rows[0]['id'], 'two')
        default: str = table(rows)
        self.assertTrue(default.startswith(
            'sort-by: "last-update-time" (newest first)\n',
        ))
        self.assertNotIn('UPDATED (UTC)', default)
        self.assertNotIn('1970-', default)
        lines: list[str] = table(
            rows, show_timestamps=True,
        ).splitlines()
        self.assertEqual(lines[1], 'CWD=' + str(self.root))
        self.assertEqual(lines[2], 'HARNESS=claude')
        self.assertIn('UPDATED (UTC)', lines[4])
        self.assertIn('1970-01-01 00:01', lines[5])
        self.assertIn('1970-01-01 00:00', lines[6])
        self.assertEqual(records[1]['updated_at'], 60.5)
        self.assertNotIn('1970', table([{
            'name': 'missing', 'id': 'three', 'harness': 'claude',
        }], show_timestamps=True))

        with patch(
            'aiskillz.cli.dialogs.list_dialogs',
            return_value=rows,
        ):
            output: StringIO = StringIO()
            with redirect_stdout(output):
                self.assertEqual(dlogs_main(['-t']), 0)
        self.assertIn('UPDATED (UTC)', output.getvalue())



if __name__ == '__main__':
    unittest.main()
