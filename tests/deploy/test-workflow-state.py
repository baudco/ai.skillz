#!/usr/bin/env python3
'''
Exercise migration against disposable repositories and worktrees.

'''

import importlib.util
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
        Preserve opaque helper archives instead of blocking migration.

        Migration previously classified every archived patch or
        executable helper as pending based only on its extension. The
        fixture writes each supported helper type with an executable
        mode. A successful migration proves that their exact bytes and
        modes reach neutral state while each legacy source remains.

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
            self.assertEqual(neutral.read_bytes(), legacy.read_bytes())
            self.assertEqual(neutral.stat().st_mode & 0o777, 0o750)
            self.assertTrue(legacy.exists())

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
