#!/usr/bin/env python3
'''
Exercise migration against disposable repositories and worktrees.

'''

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'workflow_state',
    SOURCE / 'scripts/workflow-state.py',
)
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.test')
        self.write('base', 'base')
        self.git('add', 'base')
        self.git('commit', '-qm', 'fixture')

    def git(self, *args: str) -> bytes:
        return subprocess.check_output(
            ['git', '-C', str(self.root), *args],
            stderr=subprocess.DEVNULL,
        )

    def write(self, name: str, text: str) -> Path:
        path: Path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def migrate(self) -> dict:
        plan: dict = STATE.preview(self.root)
        self.assertEqual(plan['blockers'], [])
        return STATE.apply(self.root, plan['sha256'])

    def test_fresh_and_legacy_selection(self) -> None:
        self.assertEqual(
            STATE.inspect(self.root)['backend'], 'neutral'
        )
        self.write(
            STATE.PATHS['commit_messages'][0] + '/msg.md', 'msg'
        )
        self.assertEqual(
            STATE.inspect(self.root)['backend'], 'legacy'
        )

    def test_preview_is_read_only(self) -> None:
        before: set = {
            p for p in self.root.rglob('*')
            if '.git' not in p.relative_to(self.root).parts
        }
        STATE.preview(self.root)
        after: set = {
            p for p in self.root.rglob('*')
            if '.git' not in p.relative_to(self.root).parts
        }
        self.assertEqual(before, after)

    def test_migration_preserves_index_and_originals(self) -> None:
        source: str = STATE.PATHS['commit_style'][0]
        self.write(source, 'style')
        self.git('add', source)
        self.write('pending', 'staged')
        self.git('add', 'pending')
        before: bytes = self.git('ls-files', '--stage')
        self.migrate()
        self.assertEqual(before, self.git('ls-files', '--stage'))
        self.assertEqual((self.root / source).read_text(), 'style')
        self.assertEqual(STATE.inspect(self.root)['blockers'], [])
        self.assertEqual(self.migrate()['backend'], 'neutral')
        self.git('check-ignore', '-q', '.ai/state/test')
        self.assertEqual(
            subprocess.call(
                ['git', 'check-ignore', '-q', STATE.MARKER],
                cwd=self.root,
            ),
            1,
        )

    def test_conflicts_and_stale_preview_do_not_write(self) -> None:
        old, new = STATE.PATHS['commit_style']
        self.write(old, 'old')
        plan: dict = STATE.preview(self.root)
        self.write(old, 'changed')
        with self.assertRaisesRegex(ValueError, 'Preview changed'):
            STATE.apply(self.root, plan['sha256'])
        self.write(new, 'different')
        self.assertTrue(STATE.preview(self.root)['blockers'])
        self.assertFalse((self.root / STATE.MARKER).exists())

    def test_identical_destination_and_late_legacy_write(
        self,
    ) -> None:
        old, new = STATE.PATHS['commit_style']
        self.write(old, 'same')
        self.write(new, 'same')
        self.migrate()
        self.write(new, 'new guidance')
        self.assertEqual(STATE.inspect(self.root)['blockers'], [])
        self.write(old, 'late write')
        self.assertIn(
            'Legacy files changed after migration',
            STATE.inspect(self.root)['blockers'],
        )

    def test_context_rewrite_preserves_archive_bytes(self) -> None:
        old, new = STATE.PATHS['review_context']
        text: str = STATE.PATHS['commit_messages'][0] + '/msg.md'
        self.write(old, text)
        archive: str = STATE.PATHS['commit_messages'][0] + '/msg.md'
        self.write(archive, text)
        self.migrate()
        self.assertEqual(
            (self.root / new).read_text(),
            STATE.PATHS['commit_messages'][1] + '/msg.md',
        )
        self.assertEqual(
            (self.root / STATE.destination(archive)).read_text(),
            text,
        )

    def test_archived_helpers_preserve_bytes_and_modes(self) -> None:
        '''
        Preserve opaque helper archives instead of blocking
        migration.

        Migration previously classified every archived patch or
        executable helper as pending based only on its extension. The
        fixture writes each supported helper type with an executable
        mode. A successful migration proves that their exact bytes
        and modes reach neutral state while each legacy source
        remains.

        '''
        sources: list[str] = []
        suffix: str
        for suffix in ('.patch', '.py', '.sh', '.xsh'):
            source: str = (
                STATE.PATHS['commit_messages'][0]
                + '/helper'
                + suffix
            )
            path: Path = self.write(source, f'helper {suffix}\n')
            path.chmod(0o750)
            sources.append(source)

        self.assertEqual(STATE.preview(self.root)['blockers'], [])
        self.migrate()
        for source in sources:
            legacy: Path = self.root / source
            neutral: Path = self.root / STATE.destination(source)
            self.assertEqual(
                neutral.read_bytes(), legacy.read_bytes(),
            )
            self.assertEqual(neutral.stat().st_mode & 0o777, 0o750)
            self.assertTrue(legacy.exists())

    def test_managed_roots_reject_wrong_kinds(self) -> None:
        '''
        `files()` accepted either kind for every `PATHS` role,
        migrating guidance directories and archive files into
        unusable destinations. Put the wrong kind at each managed
        root in both layouts, including empty directories. Inspection
        and preview must reject before creating workflow state.

        '''
        directories: set[str] = {
            'commit_messages', 'pr_messages', 'review_replies',
        }
        for key, pair in STATE.PATHS.items():
            for relative in pair:
                with self.subTest(key=key, relative=relative):
                    path: Path = self.root / relative
                    if key in directories:
                        self.write(relative, 'not a directory')
                    else:
                        path.mkdir(parents=True)
                    try:
                        with self.assertRaisesRegex(
                            ValueError, 'Managed path must be',
                        ):
                            STATE.inspect(self.root)
                        with self.assertRaises(ValueError):
                            STATE.preview(self.root)
                        self.assertFalse(
                            (self.root / STATE.MARKER).exists()
                        )
                    finally:
                        if path.is_dir():
                            path.rmdir()
                        else:
                            path.unlink()

    def test_chmod_invalidates_approved_preview(self) -> None:
        '''
        Preview used only byte hashes although apply copied modes.
        Change an archived helper's executable bit after preview;
        its new digest must differ and the old pin must be refused
        without creating the destination or changing the real index.

        '''
        relative: str = STATE.PATHS['commit_messages'][0] + '/run.sh'
        source: Path = self.write(relative, 'helper')
        source.chmod(0o600)
        plan: dict = STATE.preview(self.root)
        before: bytes = self.git('ls-files', '--stage')
        source.chmod(0o750)
        self.assertNotEqual(
            plan['sha256'], STATE.preview(self.root)['sha256'],
        )
        with self.assertRaisesRegex(ValueError, 'Preview changed'):
            STATE.apply(self.root, plan['sha256'])
        self.assertEqual(before, self.git('ls-files', '--stage'))
        self.assertFalse(
            (self.root / STATE.destination(relative)).exists()
        )

    def test_identical_destination_requires_matching_mode(
        self,
    ) -> None:
        '''
        Equal destination bytes previously bypassed mode validation.
        Offer the same archived helper with an executable source but
        a nonexecutable target. Preview must block, and application
        must leave both files unchanged rather than report migration.

        '''
        relative: str = STATE.PATHS['commit_messages'][0] + '/run.sh'
        source: Path = self.write(relative, 'helper')
        target: Path = self.write(
            STATE.destination(relative), 'helper',
        )
        source.chmod(0o750)
        target.chmod(0o600)
        plan: dict = STATE.preview(self.root)
        self.assertIn(
            'Destination conflict: ' + STATE.destination(relative),
            plan['blockers'],
        )
        with self.assertRaisesRegex(
            ValueError, 'Destination conflict',
        ):
            STATE.apply(self.root, plan['sha256'])
        self.assertEqual(source.stat().st_mode & 0o777, 0o750)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_mode_change_during_apply_rolls_back(self) -> None:
        '''
        Recomputing preview alone cannot catch changes after setup.
        Change the source mode at that deterministic boundary without
        changing bytes. Apply must reject the drift, restore ignores,
        and publish neither copied state nor backend selection.

        '''
        relative: str = STATE.PATHS['commit_messages'][0] + '/run.sh'
        source: Path = self.write(relative, 'helper')
        source.chmod(0o600)
        ignore: Path = self.write('.gitignore', '# user-owned\n')
        plan: dict = STATE.preview(self.root)
        original = STATE.setup

        def changed(root: Path, write: bool = True) -> None:
            '''
            Order source-mode drift after the approved preview.

            '''
            original(root, write=write)
            if write:
                source.chmod(0o750)

        with patch.object(STATE, 'setup', side_effect=changed):
            with self.assertRaisesRegex(
                ValueError, 'Source changed',
            ):
                STATE.apply(self.root, plan['sha256'])
        self.assertEqual(ignore.read_text(), '# user-owned\n')
        self.assertFalse(
            (self.root / STATE.destination(relative)).exists()
        )
        self.assertFalse((self.root / STATE.MARKER).exists())
        self.assertFalse((self.root / STATE.RECEIPT).exists())

    def test_recovery_detects_legacy_mode_drift(self) -> None:
        '''
        A successful receipt formerly recorded only source bytes.
        Migrate a helper, then change only its legacy executable bit.
        Resolution must expose the late write while the neutral copy
        retains the mode approved in the migration preview.

        '''
        relative: str = STATE.PATHS['commit_messages'][0] + '/run.sh'
        source: Path = self.write(relative, 'helper')
        source.chmod(0o600)
        self.migrate()
        source.chmod(0o750)
        self.assertIn(
            'Legacy modes changed after migration',
            STATE.inspect(self.root)['blockers'],
        )
        target: Path = self.root / STATE.destination(relative)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_byte_only_recovery_receipt_remains_readable(
        self,
    ) -> None:
        '''
        Existing consumers have receipts from byte-only previews.
        Remove the new mode field to model one of those receipts;
        unchanged sources must still resolve, while a subsequent
        source-byte change remains blocked by the original inventory.

        '''
        relative: str = STATE.PATHS['commit_style'][0]
        self.write(relative, 'style')
        self.migrate()
        receipt: Path = self.root / STATE.RECEIPT
        saved: dict = json.loads(receipt.read_text())
        saved.pop('legacy_modes', None)
        receipt.write_text(json.dumps(saved))
        self.assertEqual(STATE.inspect(self.root)['blockers'], [])
        self.write(relative, 'changed')
        self.assertIn(
            'Legacy files changed after migration',
            STATE.inspect(self.root)['blockers'],
        )

    def test_symlink_layout_refused(self) -> None:
        '''
        Reject a neutral root that could escape repository isolation.

        A symlinked `.ai` directory could redirect migrated state
        outside the worktree. The fixture points it at legacy state;
        preview must reject the unsafe path before writing anything.

        '''
        (self.root / '.ai').symlink_to(
            self.root / '.claude', target_is_directory=True
        )
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            STATE.preview(self.root)

    def test_failure_restores_ignore_and_keeps_backend(self) -> None:
        self.write(STATE.PATHS['commit_style'][0], 'style')
        self.write('.gitignore', '# owned by user\n')
        plan: dict = STATE.preview(self.root)
        with patch.object(
            STATE, 'select', side_effect=OSError('fail')
        ):
            with self.assertRaises(OSError):
                STATE.apply(self.root, plan['sha256'])
        self.assertEqual(
            (self.root / '.gitignore').read_text(),
            '# owned by user\n',
        )
        self.assertFalse((self.root / STATE.RECEIPT).exists())
        self.assertFalse((self.root / STATE.MARKER).exists())
        self.assertEqual(
            STATE.inspect(self.root)['backend'], 'legacy'
        )

    def test_additional_provider_data_blocks(self) -> None:
        self.write(
            '.opencode/skills/commit-msg/conf.toml', 'private'
        )
        self.assertTrue(STATE.preview(self.root)['blockers'])

    def test_neutral_selection_with_legacy_data(self) -> None:
        self.write(
            STATE.MARKER, '{"version": 1, "backend": "neutral"}',
        )
        self.write(STATE.PATHS['commit_style'][0], 'style')
        self.assertTrue(STATE.inspect(self.root)['blockers'])
        self.assertEqual(self.migrate()['blockers'], [])

    def test_broad_ignore_rejects_before_writes(self) -> None:
        self.write('.gitignore', '/.ai/\n')
        with self.assertRaisesRegex(ValueError, 'Configuration'):
            STATE.preview(self.root)
        self.assertFalse((self.root / STATE.MARKER).exists())

    def test_prepare_cli_selects_once(self) -> None:
        self.write(STATE.PATHS['commit_style'][0], 'style')
        command: list[str] = [
            'bash', str(SOURCE / 'scripts/deploy.sh'),
            'runtime', 'prepare', str(self.root),
        ]
        subprocess.check_output(command)
        first: bytes = (self.root / STATE.MARKER).read_bytes()
        subprocess.check_output(command)
        self.assertEqual(first,
                         (self.root / STATE.MARKER).read_bytes())
        self.assertEqual(
            STATE.inspect(self.root)['backend'], 'legacy',
        )

    def test_worktree_state_is_local(self) -> None:
        worktree: Path = self.root / 'worktree'
        self.git('worktree', 'add', '-qb', 'isolated', str(worktree))
        plan: dict = STATE.preview(worktree)
        STATE.apply(worktree, plan['sha256'])
        self.assertTrue((worktree / STATE.MARKER).exists())
        self.assertFalse((self.root / STATE.MARKER).exists())


if __name__ == '__main__':
    unittest.main()
