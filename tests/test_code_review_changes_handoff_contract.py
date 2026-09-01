import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (
    ROOT / 'skills' / 'code-review-changes' / 'SKILL.md'
).read_text()
DEPLOY = (
    ROOT / 'skills' / 'code-review-changes' / 'DEPLOY.md'
).read_text()
HANDOFF = (
    ROOT
    / 'skills'
    / 'code-review-changes'
    / 'references'
    / 'review-adjustment-handoff.md'
).read_text()


def _git(root, *args, index=None):
    env = os.environ.copy()
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    result = subprocess.run(
        ['git', *args],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


class ReviewAdjustmentHandoffTests(unittest.TestCase):
    def test_parent_skill_captures_and_reports_the_handoff(self):
        '''
        A final-only handoff cannot reconstruct the pre-edit
        baseline.

        The parent workflow must enter the shared contract before its
        first edit and return to it after verification. This test
        pins both integration points and the optional commit-plan
        dependency.

        '''
        reference = 'references/review-adjustment-handoff.md'
        self.assertEqual(SKILL.count(f']({reference})'), 2)
        self.assertIn('Before the first edit', SKILL)
        self.assertIn('plan-refresh handoff', SKILL)
        self.assertIn('`/commit-plan`', DEPLOY)
        self.assertIn('optional post-fix handoff', DEPLOY)

    def test_private_baseline_does_not_mutate_the_real_index(self):
        '''
        Staged and unstaged Tuicr reviews need the same pre-edit
        anchor.

        A private index can snapshot selected tracked and untracked
        paths without staging them in the user's index. These
        assertions retain worktree-specific storage, selected-path
        scope, and the final real index equivalence check.

        '''
        self.assertIn(
            'Build a private temporary index from `HEAD`',
            HANDOFF,
        )
        self.assertIn('Use `GIT_INDEX_FILE`', HANDOFF)
        self.assertIn('git rev-parse --git-path', HANDOFF)
        self.assertIn(
            'real index tree and stage entries are unchanged',
            HANDOFF,
        )
        self.assertIn(
            'do not include\nignored, secret, or unrelated paths',
            HANDOFF,
        )

    def test_commands_cover_new_deleted_and_mixed_owned_paths(self):
        '''
        Plain `git diff` omits new files and path-level adds can
        overstage.

        The contract must expose new paths with intent-to-add,
        compare against the captured tree, include deletions with
        `git add -A`, and require hunk selection for unrelated work.

        '''
        self.assertIn('git add --intent-to-add --', HANDOFF)
        self.assertIn(
            'git diff --find-renames <pre-review-tree> --',
            HANDOFF,
        )
        self.assertIn('git add -A --', HANDOFF)
        self.assertIn('git add -p --', HANDOFF)
        self.assertIn(
            'do not fabricate an empty `git add` command',
            HANDOFF,
        )
        self.assertIn('Do not stage anything', HANDOFF)

    def test_review_changes_invalidate_pending_boundaries(self):
        '''
        Refactors after planning can invalidate boundaries and
        messages.

        This test prevents reuse of an archived commit command after
        files split or message context changes. It preserves
        `/commit-plan` as the owner of refreshed boundaries, checks,
        messages, and the editor-gated commit command.

        '''
        self.assertIn(
            'affected uncommitted boundary and its transitive '
            'dependants as stale',
            HANDOFF,
        )
        self.assertIn(
            'added, deleted, renamed, split, or combined',
            HANDOFF,
        )
        self.assertIn(
            'Never reuse or render a prior archived message',
            HANDOFF,
        )
        self.assertIn(
            'present `/commit-plan` as the next invocation',
            HANDOFF,
        )
        self.assertIn(
            'Do not substitute a\nstale message, direct commit '
            'command',
            HANDOFF,
        )
        self.assertIn(
            'never edits a commit\nplan receipt',
            HANDOFF,
        )

    def test_private_tree_isolates_review_adjustments(self):
        '''
        An unstaged reviewed baseline must not appear as a review
        fix.

        The test creates a real temporary repository, snapshots one
        unstaged reviewed file through a private index, then adds a
        fix and a new file. It proves the real index stays unchanged,
        the baseline diff shows only the later fix, intent-to-add
        exposes the new path, and the final add stages both files.

        '''
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            tracked = root / 'tracked.txt'
            created = root / 'created.txt'
            private_index = root / 'review.index'

            _git(root, 'init', '-q')
            _git(root, 'config', 'user.name', 'Test User')
            _git(root, 'config', 'user.email', 'test@example.com')
            tracked.write_text('base\n')
            _git(root, 'add', '--', tracked.name)
            _git(root, 'commit', '-qm', 'base')

            tracked.write_text('base\nreviewed-baseline\n')
            starting_index = _git(root, 'ls-files', '--stage')
            _git(root, 'read-tree', 'HEAD', index=private_index)
            _git(
                root,
                'add',
                '-A',
                '--',
                tracked.name,
                index=private_index,
            )
            baseline_tree = _git(
                root,
                'write-tree',
                index=private_index,
            ).strip()
            self.assertEqual(
                _git(root, 'ls-files', '--stage'),
                starting_index,
            )
            private_index.unlink()

            tracked.write_text(
                'base\nreviewed-baseline\nreview-adjustment\n'
            )
            created.write_text('review-created\n')
            _git(root, 'add', '--intent-to-add', '--', created.name)
            patch = _git(
                root,
                'diff',
                baseline_tree,
                '--',
                tracked.name,
                created.name,
            )
            self.assertIn('+review-adjustment', patch)
            self.assertNotIn('+reviewed-baseline', patch)
            self.assertIn('+review-created', patch)

            _git(
                root,
                'add',
                '-A',
                '--',
                tracked.name,
                created.name,
            )
            staged = _git(root, 'diff', '--cached', '--name-status')
            self.assertIn('M\ttracked.txt', staged)
            self.assertIn('A\tcreated.txt', staged)


if __name__ == '__main__':
    unittest.main()
