# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise legacy worktree associations used by the WKT display.

'''

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


from aiskillz.wkt._lookup import WktLookup


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class DialogWorktreeTests(unittest.TestCase):
    '''
    Use disposable Git metadata to verify `WktLookup` fallbacks.

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
            [
                'git',
                'init',
                '--quiet',
                str(self.root),
            ],
            capture_output=True, check=True,
        )

    def linked(self, name: str, dialog: object) -> Path:
        '''
        Write the Git and skill metadata for one linked worktree.

        '''
        root: Path = self.root.parent / name
        root.mkdir()
        admin: Path = self.root / '.git/worktrees' / name
        admin.mkdir(parents=True)
        (admin / 'HEAD').write_text('ref: refs/heads/fixture\n')
        (admin / 'commondir').write_text('../..\n')
        gitfile: Path = root / '.git'
        (admin / 'gitdir').write_text(str(gitfile) + '\n')
        gitfile.write_text(f'gitdir: {admin}\n')
        metadata: Path = admin / 'ai-skillz-wkt'
        metadata.mkdir()
        (metadata / 'owner.json').write_text(json.dumps({
            'session': 'generic-owner-token',
            'dialog': dialog,
        }))
        return root

    def test_removed_relation_warns_and_resumes_saved_checkout(
        self,
    ) -> None:
        '''
        A removed recorded WKT used to block a valid dialog resume.

        Record a new WKT for a dialog saved in another live linked
        checkout, then remove the new WKT's Git file. Lookup must
        retain the recorded identity but return no active path.
        Resume must name the unavailable WKT and continue using the
        existing saved cwd instead of requiring an override.
        Listing must distinguish this relation from an unknown WKT.
        Remove the Git backlink to reproduce failed verification;
        assert both CLI outputs and that --cwd still overrides it.
        Other dialogs retain ordinary fallback.

        '''
        from aiskillz import record_wkt_relation
        from aiskillz._resume import resume_target
        from aiskillz.cli import format_dialog_table, resume_main

        old: Path = self.linked('old', {})
        new: Path = self.linked('new', {})
        record_wkt_relation(
            str(self.root), 'claude', 'dialog', str(new),
        )
        (new / '.git').unlink()
        lookup: WktLookup = WktLookup()
        self.assertEqual(
            lookup.roots(str(old), 'claude', 'dialog'), set(),
        )
        self.assertTrue(
            lookup.has_relation(str(old), 'claude', 'dialog'),
        )
        self.assertEqual(
            lookup.recorded_roots(str(old), 'claude', 'dialog'),
            {str(new)},
        )
        self.assertEqual(
            lookup.roots(str(old), 'claude', 'unrecorded'),
            {str(old)},
        )
        dialog: dict = {
            'name': 'Example',
            'id': 'dialog',
            'harness': 'claude',
            'cwd': str(old),
        }
        self.assertIn(
            'new (unavailable)', format_dialog_table([dialog]),
        )
        with patch(
            'aiskillz._resume.dialogs.list_dialogs',
            return_value=[dialog],
        ):
            target: dict = resume_target('Example')
            self.assertEqual(target['cwd'], str(old))
            self.assertIn(str(new), target['warnings'][0])
            stderr: Mock
            with (
                patch(
                    'aiskillz.cli.resume_target',
                    return_value=target,
                ),
                patch('aiskillz.cli.sys.stderr') as stderr,
            ):
                with patch(
                    'aiskillz.cli.shutil.which',
                    return_value='/bin/claude',
                ):
                    with patch('aiskillz.cli.subprocess.run') as run:
                        run.return_value.returncode = 0
                        self.assertEqual(resume_main(['Example']), 0)
                        self.assertEqual(
                            run.call_args.kwargs['cwd'], str(old),
                        )
                self.assertIn(
                    str(new), str(stderr.write.call_args_list),
                )
            self.assertEqual(
                resume_target('Example', cwd=str(old))['cwd'],
                str(old),
            )

    def test_explicit_owner_overrides_saved_main_cwd(self) -> None:
        '''
        A dialog opened at main can work in a linked checkout.

        Record its verified ID separately from the generic ownership
        token. Lookups from main must find that worktree, distinguish
        harnesses sharing IDs, and retain Git fallback for other IDs.
        Repeated lookups must reuse this rendering's Git inventory.

        '''
        root: Path = self.linked('feature', {
            'harness': 'codex',
            'id': 'dialog-one',
        })
        labels: WktLookup = WktLookup()
        self.assertEqual(
            labels.roots(str(self.root), 'codex', 'dialog-one'),
            {str(root)},
        )
        with patch(
            'aiskillz.wkt._lookup.checkout_location',
        ) as query:
            self.assertEqual(
                labels.roots(str(self.root), 'codex', 'dialog-one'),
                {str(root)},
            )
            query.assert_not_called()

        self.assertEqual(
            labels.roots(str(self.root), 'claude', 'dialog-one'),
            set(),
        )
        self.assertEqual(
            labels.roots(str(root), 'claude', 'other'), {str(root)},
        )

    def test_multiple_and_removed_worktrees(self) -> None:
        '''
        One dialog can accumulate two live ownership associations.

        Do not choose by filesystem iteration order. Mark ambiguity,
        then remove one checkout while leaving stale admin metadata.
        A fresh rendering must ignore that removed worktree.

        '''
        dialog: dict = {'harness': 'opencode', 'id': 'ses_one'}
        first: Path = self.linked('first', dialog)
        second: Path = self.linked('second', dialog)
        self.assertEqual(
            WktLookup().roots(
                str(self.root), 'opencode', 'ses_one',
            ),
            {str(first), str(second)},
        )
        (second / '.git').unlink()
        second.rmdir()
        self.assertEqual(
            WktLookup().roots(
                str(self.root), 'opencode', 'ses_one',
            ),
            {str(first)},
        )

    def test_unknown_owner_and_malformed_metadata(self) -> None:
        '''
        Legacy session tokens are not authoritative dialog IDs.

        Null and malformed dialog fields must provide no association,
        while a cwd inside that worktree still gets the Git fallback.
        A broken JSON owner file must not prevent table rendering.

        '''
        root: Path = self.linked('old', None)
        self.assertEqual(
            WktLookup().roots(
                str(self.root), 'codex', 'generic-owner-token',
            ),
            set(),
        )
        owner: Path = (
            self.root / '.git/worktrees/old/ai-skillz-wkt/owner.json'
        )
        owner.write_text('{broken')
        self.assertEqual(
            WktLookup().roots(str(root), 'codex', 'one'),
            {str(root)},
        )

if __name__ == '__main__':
    unittest.main()
