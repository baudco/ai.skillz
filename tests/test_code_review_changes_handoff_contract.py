import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT: Path = Path(__file__).resolve().parents[1]
SKILL: str = (
    ROOT / 'skills' / 'code-review-changes' / 'SKILL.md'
).read_text()
DEPLOY: str = (
    ROOT / 'skills' / 'code-review-changes' / 'DEPLOY.md'
).read_text()
HANDOFF: str = (
    ROOT
    / 'skills'
    / 'code-review-changes'
    / 'references'
    / 'review-adjustment-handoff.md'
).read_text()


def _git(
    root: Path,
    *args: str,
    index: Path|None = None,
) -> str:
    '''
    Run Git in the disposable fixture, optionally using `index`.

    - Strip ambient Git routing/configuration so the fixture cannot
      address the caller's repository or real index accidentally.
    - Return stdout; failed commands retain their argv and captured
      diagnostics in `subprocess.CalledProcessError`.

    '''
    env: dict[str, str] = os.environ.copy()
    key: str
    for key in tuple(env):
        if key.startswith('GIT_'):
            env.pop(key)

    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)

    result: subprocess.CompletedProcess[str] = subprocess.run(
        ['git', '-c', 'core.fsmonitor=false', *args],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout


def _review_tree(root: Path, base: str, *paths: str) -> str:
    '''
    Snapshot selected fixture paths without changing its real index.

    - Start from `base`; callers select existing or tracked paths,
      including deletions and both sides of a rename.
    - Keep `private_index` in this worktree's Git directory, not a
      shared location. Its lifetime ends after writing the tree.

    '''
    git_dir: Path = Path(
        _git(root, 'rev-parse', '--absolute-git-dir').strip()
    )
    directory: str
    with tempfile.TemporaryDirectory(
        prefix='review-index-',
        dir=git_dir,
    ) as directory:
        private_index: Path = Path(directory) / 'index'
        _git(root, 'read-tree', base, index=private_index)
        _git(root, 'add', '-A', '--', *paths, index=private_index)
        tree: str = _git(
            root, 'write-tree', index=private_index,
        ).strip()

    return tree


class ReviewAdjustmentHandoffTests(unittest.TestCase):
    '''
    Verify handoff policy and its real-Git snapshot behavior.

    '''

    def test_parent_skill_captures_and_reports_the_handoff(
        self,
    ) -> None:
        '''
        A final-only handoff cannot reconstruct the pre-edit
        baseline.

        The parent workflow must enter the shared contract before its
        first edit and return to it after verification. This test
        pins both integration points and the optional commit-plan
        dependency.

        '''
        reference: str = 'references/review-adjustment-handoff.md'
        self.assertEqual(SKILL.count(f']({reference})'), 2)
        self.assertIn('Before the first edit', SKILL)
        self.assertIn('plan-refresh handoff', SKILL)
        self.assertIn('`/commit-plan`', DEPLOY)
        self.assertIn('optional post-fix handoff', DEPLOY)
        self.assertIn('Pre-staging is not required', DEPLOY)
        self.assertIn('explicit rule-by-rule style', SKILL)
        self.assertIn('human-readability pass', SKILL)
        self.assertIn('complete touched function', SKILL)
        self.assertIn('remaining gaps', SKILL)

    def test_private_baseline_does_not_mutate_the_real_index(
        self,
    ) -> None:
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

    def test_default_review_is_plan_first(self) -> None:
        '''
        Keep the extracted `HANDOFF` from restoring staging-first.

        - The old reference required intent-to-add for new files and
          staging before planning, contradicting the newer skill.
        - Check the default section separately from its opt-in route:
          compare private trees and route directly to planning.
        - Retain index ownership and local-reply cleanup constraints.

        '''
        default_and_optional: str = HANDOFF.split(
            '### Default: review without changing the real index', 1,
        )[1]
        default: str = default_and_optional.split(
            '### Optional: explicitly chosen manual staging', 1,
        )[0]
        self.assertIn('<post-review-tree>', default)
        self.assertIn(
            'git diff --find-renames <pre-review-tree> '
            '<post-review-tree> --',
            default,
        )
        self.assertIn(
            'Default next step: review the diff, '
            'then invoke `/commit-plan`.',
            default,
        )
        self.assertNotIn('git add --intent-to-add --', default)
        self.assertNotIn('git add -p --', default)
        self.assertIn('Do not unstage', HANDOFF)
        self.assertIn(
            'Local `-r` replies do not authorize staging', HANDOFF,
        )
        self.assertIn('actual staging, not the completion', HANDOFF)

    def test_commands_cover_new_deleted_and_mixed_owned_paths(
        self,
    ) -> None:
        '''
        Plain `git diff` omits new files and path-level adds can
        overstage.

        After explicit human selection, `HANDOFF` must still expose
        new paths with intent-to-add, include deletions with
        `git add -A`, and require hunk selection for unrelated work.
        Their opt-in placement preserves capability without making
        real-index mutation the default review step.

        '''
        optional: str = HANDOFF.split(
            '### Optional: explicitly chosen manual staging', 1,
        )[1].split('## Refresh Commit Plans', 1)[0]
        self.assertIn(
            'Only when the human explicitly chooses', optional,
        )
        self.assertIn('git add --intent-to-add --', optional)
        self.assertIn(
            'git diff --find-renames <pre-review-tree> --',
            optional,
        )
        self.assertIn('git add -A --', optional)
        self.assertIn('git add -p --', optional)
        self.assertIn(
            'do not fabricate an empty `git add` command',
            HANDOFF,
        )
        self.assertIn('Do not stage anything', HANDOFF)

    def test_review_changes_invalidate_pending_boundaries(
        self,
    ) -> None:
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
        self.assertIn('cached plan-executor invocations', HANDOFF)
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

    def test_private_tree_isolates_review_adjustments(self) -> None:
        '''
        Show all review adjustments while preserving `real_index`.

        - The old live-diff route used real-index intent-to-add to
          reveal new files, violating the default ownership boundary.
        - Exercise staged and unstaged baselines, an untracked note,
          unrelated staged work, new files, deletion and rename.
          `_review_tree` captures both ends privately.
        - Compare the patch, real index bytes/entries and HEAD.
          Pre-review changes must not be reported as fixes;
          untracked paths must remain absent from the real index.

        '''
        staged_baseline: bool
        for staged_baseline in (False, True):
            with self.subTest(staged_baseline=staged_baseline):
                value: str
                with tempfile.TemporaryDirectory() as value:
                    root: Path = Path(value)
                    tracked: Path = root / 'tracked file.txt'
                    created: Path = root / 'review created.txt'
                    note: Path = root / 'existing-note.txt'
                    deleted: Path = root / 'deleted.txt'
                    renamed: Path = root / 'old-name.txt'
                    destination: Path = root / 'new-name.txt'
                    unrelated: Path = root / 'unrelated.txt'

                    _git(root, 'init', '-q')
                    _git(root, 'config', 'user.name', 'Test User')
                    _git(
                        root, 'config', 'user.email',
                        'test@example.com',
                    )
                    tracked.write_text('base\n')
                    deleted.write_text('remove-me\n')
                    renamed.write_text('rename-me\n')
                    unrelated.write_text('original\n')
                    _git(
                        root, 'add', '--', tracked.name,
                        deleted.name, renamed.name, unrelated.name,
                    )
                    _git(root, 'commit', '-qm', 'base')
                    tracked.write_text('base\nreviewed-baseline\n')
                    if staged_baseline:
                        _git(root, 'add', '--', tracked.name)

                    note.write_text('existing-note\n')
                    unrelated.write_text('unrelated user work\n')
                    _git(root, 'add', '--', unrelated.name)
                    real_index: Path = root / '.git' / 'index'
                    starting_index: bytes = real_index.read_bytes()
                    starting_entries: str = _git(
                        root, 'ls-files', '--stage', '--debug', '-z',
                    )
                    starting_head: str = _git(
                        root, 'rev-parse', 'HEAD',
                    )
                    baseline_tree: str = _review_tree(
                        root, 'HEAD', tracked.name, note.name,
                        deleted.name, renamed.name,
                    )
                    self.assertEqual(
                        real_index.read_bytes(), starting_index,
                    )

                    tracked.write_text(
                        'base\nreviewed-baseline\n'
                        'review-adjustment\n'
                    )
                    note.write_text('existing-note\nreview-note\n')
                    created.write_text('review-created\n')
                    deleted.unlink()
                    renamed.rename(destination)
                    post_review_tree: str = _review_tree(
                        root, baseline_tree, tracked.name, note.name,
                        created.name, deleted.name, renamed.name,
                        destination.name,
                    )
                    patch: str = _git(
                        root, 'diff', '--find-renames',
                        baseline_tree, post_review_tree, '--',
                        tracked.name, note.name, created.name,
                        deleted.name, renamed.name, destination.name,
                    )
                    self.assertIn('+review-adjustment', patch)
                    self.assertNotIn('+reviewed-baseline', patch)
                    self.assertIn('+review-note', patch)
                    self.assertNotIn('+existing-note', patch)
                    self.assertIn('+review-created', patch)
                    self.assertIn('-remove-me', patch)
                    self.assertIn('rename from old-name.txt', patch)
                    self.assertIn('rename to new-name.txt', patch)
                    self.assertNotIn('unrelated user work', patch)
                    self.assertEqual(
                        real_index.read_bytes(), starting_index,
                    )
                    self.assertEqual(
                        _git(
                            root, 'ls-files', '--stage',
                            '--debug', '-z',
                        ),
                        starting_entries,
                    )
                    self.assertEqual(
                        _git(root, 'rev-parse', 'HEAD'),
                        starting_head,
                    )

    def test_explicit_staging_route_remains_available(self) -> None:
        '''
        Preserve the explicit manual route alongside private review.

        - A user may still choose a single-commit staging handoff.
        - Intent-to-add exposes the new file in a live baseline diff;
          the subsequent scoped add stages both reviewed paths.
        - This fixture deliberately mutates its real index only for
          that opted-in route, never as a prerequisite for planning.

        '''
        value: str
        with tempfile.TemporaryDirectory() as value:
            root: Path = Path(value)
            tracked: Path = root / 'tracked.txt'
            created: Path = root / 'created.txt'

            _git(root, 'init', '-q')
            _git(root, 'config', 'user.name', 'Test User')
            _git(root, 'config', 'user.email', 'test@example.com')
            tracked.write_text('base\n')
            _git(root, 'add', '--', tracked.name)
            _git(root, 'commit', '-qm', 'base')

            tracked.write_text('base\nreviewed-baseline\n')
            baseline_tree: str = _review_tree(
                root, 'HEAD', tracked.name,
            )

            tracked.write_text(
                'base\nreviewed-baseline\nreview-adjustment\n'
            )
            created.write_text('review-created\n')
            _git(root, 'add', '--intent-to-add', '--', created.name)
            patch: str = _git(
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
            staged: str = _git(
                root, 'diff', '--cached', '--name-status',
            )
            self.assertIn('M\ttracked.txt', staged)
            self.assertIn('A\tcreated.txt', staged)


if __name__ == '__main__':
    unittest.main()
