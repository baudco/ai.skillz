import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / 'skills'
    / 'commit-plan'
    / 'scripts'
    / 'plan-exec.py'
)


class CommitPlanExecTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Plan Test')
        self.git('config', 'user.email', 'plan@example.invalid')
        (self.root / 'base.txt').write_text('base\n')
        (self.root / 'fixturepkg.py').write_text('VALUE = "tree"\n')
        self.git('add', 'base.txt', 'fixturepkg.py')
        self.git('commit', '-q', '-m', 'base')
        self.initial_parent = self.git(
            'rev-parse',
            'HEAD',
        ).stdout.strip()
        self.initial_tree = self.git(
            'rev-parse',
            'HEAD^{tree}',
        ).stdout.strip()
        (self.root / 'one.txt').write_text('one\n')
        (self.root / 'two.txt').write_text('two\n')
        self.tree_one = self.index_tree('one.txt')
        self.tree_two = self.index_tree('one.txt', 'two.txt')
        (self.root / 'fixturepkg.py').write_text('VALUE = "live"\n')
        self.runtime = (
            self.root
            / '.claude'
            / 'skills'
            / 'commit-msg'
            / 'msgs'
            / 'test-runtime'
        )
        self.runtime.mkdir(parents=True)
        self.check_count = self.runtime / 'check-count'
        self.editor_count = self.runtime / 'editor-count'
        self.editor_sentinel = self.runtime / 'editor-sentinel'
        self.check_script = self.make_check_script()
        self.editor_script = self.make_editor_script()
        self.messages = [
            self.make_message('one.md', 'Add one'),
            self.make_message('two.md', 'Add two'),
        ]
        self.patches = [
            self.make_patch(
                'one.patch',
                self.initial_tree,
                self.tree_one,
            ),
            self.make_patch(
                'two.patch',
                self.tree_one,
                self.tree_two,
            ),
        ]
        self.spec_path = self.runtime / 'plan.json'
        self.write_spec()

    def run_process(
        self,
        arguments,
        *,
        check=True,
        env=None,
    ):
        result = subprocess.run(
            arguments,
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        if check and result.returncode:
            self.fail(
                f'command failed: {arguments!r}\n'
                f'{result.stdout}{result.stderr}'
            )
        return result

    def git(self, *arguments, check=True):
        return self.run_process(
            ['git', *arguments],
            check=check,
        )

    def index_tree(self, *paths):
        self.git('add', '--', *paths)
        tree = self.git('write-tree').stdout.strip()
        self.git('read-tree', 'HEAD')
        return tree

    def make_check_script(self):
        path = self.runtime / 'record-check.sh'
        path.write_text(
            '#!/bin/sh\n'
            'root=$(pwd -P) || exit 2\n'
            'test "$(git rev-parse --show-toplevel)" = "$root" '
            '|| exit 3\n'
            'gitdir=$(git rev-parse --absolute-git-dir) || exit 4\n'
            'case "$gitdir" in "$root"/*) ;; *) exit 5 ;; esac\n'
            'git rev-parse HEAD^ >/dev/null || exit 6\n'
            'test "$AI_SKILLZ_BOUNDARY_ROOT" = "$root" || exit 7\n'
            'test -z "${PYTHONPATH+x}" || exit 8\n'
            'test "$PLAN_TEST_ENV" = yes || exit 9\n'
            'test -e "$2" || exit 10\n'
            'if test "$3" != -; then test ! -e "$3" || exit 11; fi\n'
            'printf "x\\n" >> "$1"\n'
        )
        path.chmod(0o755)
        return path

    def make_editor_script(self):
        path = self.runtime / 'editor.sh'
        count = self.editor_count
        sentinel = self.editor_sentinel
        path.write_text(
            '#!/bin/sh\n'
            f'printf "x\\n" >> "{count}"\n'
            'if [ -n "$PLAN_EDITOR_FAIL_ONCE" ] '
            f'&& [ ! -e "{sentinel}" ]; then\n'
            f'  touch "{sentinel}"\n'
            '  exit 1\n'
            'fi\n'
            'exit 0\n'
        )
        path.chmod(0o755)
        return path

    def make_message(self, name, subject):
        path = self.runtime / name
        path.write_text(f'{subject}\n')
        return path

    def make_patch(self, name, before_tree, after_tree):
        path = self.runtime / name
        payload = self.git(
            'diff',
            '--binary',
            before_tree,
            after_tree,
        ).stdout
        path.write_text(payload)
        return path

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def relative(self, path):
        return str(path.relative_to(self.root))

    def boundary(
        self,
        ordinal,
        tree,
        before_tree,
        expected,
        forbidden,
        patch,
        message,
    ):
        parent_tree = (
            self.initial_tree
            if ordinal == 1
            else self.tree_one
        )
        subject = f'Add boundary {ordinal}'
        return {
            'ordinal': ordinal,
            'subject': subject,
            'parent_tree': parent_tree,
            'tree': tree,
            'index_before_tree': before_tree,
            'patch': {
                'path': self.relative(patch),
                'sha256': self.digest(patch),
            },
            'message': {
                'path': self.relative(message),
                'sha256': self.digest(message),
            },
            'project_checks': [
                {
                    'argv': [
                        str(self.check_script),
                        str(self.check_count),
                        expected,
                        forbidden,
                    ],
                    'env': {'PLAN_TEST_ENV': 'yes'},
                    'resolution_argv': [
                        sys.executable,
                        '-c',
                        (
                            'import pathlib, fixturepkg; '
                            'print(pathlib.Path('
                            'fixturepkg.__file__).resolve())'
                        ),
                    ],
                },
            ],
        }

    def write_spec(self):
        common_dir = self.git(
            'rev-parse',
            '--git-common-dir',
        ).stdout.strip()
        git_dir = self.git(
            'rev-parse',
            '--git-dir',
        ).stdout.strip()
        branch = self.git(
            'symbolic-ref',
            '-q',
            'HEAD',
        ).stdout.strip()
        spec = {
            'version': 1,
            'repo_root': str(self.root.resolve()),
            'git_common_dir': str(
                (self.root / common_dir).resolve()
            ),
            'git_dir': str((self.root / git_dir).resolve()),
            'branch_ref': branch,
            'initial_parent': self.initial_parent,
            'initial_tree': self.initial_tree,
            'initial_index_tree': self.initial_tree,
            'boundaries': [
                self.boundary(
                    1,
                    self.tree_one,
                    self.initial_tree,
                    'one.txt',
                    'two.txt',
                    self.patches[0],
                    self.messages[0],
                ),
                self.boundary(
                    2,
                    self.tree_two,
                    self.tree_one,
                    'two.txt',
                    '-',
                    self.patches[1],
                    self.messages[1],
                ),
            ],
        }
        self.spec_path.write_text(json.dumps(spec, indent=2))
        self.spec_digest = self.digest(self.spec_path)

    def rewrite_spec(self, update):
        spec = json.loads(self.spec_path.read_text())
        update(spec)
        self.spec_path.write_text(json.dumps(spec, indent=2))
        self.spec_digest = self.digest(self.spec_path)

    def invoke(self, *mode, check=True, extra_env=None):
        env = os.environ.copy()
        env['GIT_EDITOR'] = str(self.editor_script)
        env['PYTHONPATH'] = str(self.root)
        if extra_env:
            env.update(extra_env)
        return self.run_process(
            [
                sys.executable,
                str(SCRIPT),
                '--spec',
                str(self.spec_path),
                '--sha256',
                self.spec_digest,
                *mode,
            ],
            check=check,
            env=env,
        )

    def line_count(self, path):
        if not path.exists():
            return 0
        return len(path.read_text().splitlines())

    def commit_count(self):
        return int(self.git('rev-list', '--count', 'HEAD').stdout)

    def test_partial_and_complete_plan_reruns_are_noops(self):
        '''
        A generated multi-boundary plan used to expose direct
        staging, checks and commit commands. After boundary one
        advanced `HEAD`, pasting the complete block again reached its
        first commit command and failed with nothing to commit, so
        execution could not resume at boundary two. This test
        executes one boundary, repeats the completed prefix, finishes
        both boundaries and repeats the full plan. Commit, check and
        editor counts prove completed boundaries perform no work; the
        final staged-tree assertion proves later user state is
        preserved.

        '''
        original_head = self.git('rev-parse', 'HEAD').stdout.strip()
        original_index = self.git('write-tree').stdout.strip()
        self.invoke('--preflight')
        shown = json.loads(self.invoke('--show').stdout)
        self.assertEqual(
            shown[0]['commit'][:4],
            ['git', 'commit', '--edit', '--file'],
        )
        self.assertEqual(
            self.git('rev-parse', 'HEAD').stdout.strip(),
            original_head,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            original_index,
        )

        self.invoke('--execute', '1')
        self.assertEqual(self.commit_count(), 2)
        self.assertEqual(
            self.git('log', '-1', '--format=%s').stdout.strip(),
            'Add one',
        )
        self.assertEqual(self.line_count(self.check_count), 1)
        self.assertEqual(self.line_count(self.editor_count), 1)

        self.invoke('--preflight')
        self.invoke('--show')
        result = self.invoke('--execute', '1')
        self.assertIn('already complete', result.stdout)
        self.assertEqual(self.line_count(self.check_count), 1)
        self.assertEqual(self.line_count(self.editor_count), 1)

        self.invoke('--execute', '2')
        self.assertEqual(self.commit_count(), 3)
        self.assertEqual(
            self.git('log', '-1', '--format=%s').stdout.strip(),
            'Add two',
        )
        self.assertEqual(self.line_count(self.check_count), 2)
        self.assertEqual(self.line_count(self.editor_count), 2)

        self.invoke('--preflight')
        self.invoke('--show')
        self.invoke('--execute', '1')
        self.invoke('--execute', '2')
        self.assertEqual(self.commit_count(), 3)
        self.assertEqual(self.line_count(self.check_count), 2)
        self.assertEqual(self.line_count(self.editor_count), 2)

        (self.root / 'later.txt').write_text('later\n')
        self.git('add', 'later.txt')
        later_index = self.git('write-tree').stdout.strip()
        self.invoke('--execute', '1')
        self.invoke('--execute', '2')
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            later_index,
        )

    def test_editor_abort_remains_pending_and_resumes(self):
        '''
        An editor cancellation must not consume a boundary or make
        its sequence unusable. The fake editor fails once after
        staging and all checks succeed, leaving `HEAD` at the
        recorded parent. Re-executing the same boundary repeats the
        safe pending work and creates exactly one commit; a third
        execution proves the completed boundary does not reopen the
        editor or duplicate that commit.

        '''
        environment = {'PLAN_EDITOR_FAIL_ONCE': '1'}
        result = self.invoke(
            '--execute',
            '1',
            check=False,
            extra_env=environment,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            self.tree_one,
        )

        self.invoke('--execute', '1', extra_env=environment)
        self.assertEqual(self.commit_count(), 2)
        attempts = self.line_count(self.editor_count)
        self.assertEqual(attempts, 2)
        self.invoke('--execute', '1', extra_env=environment)
        self.assertEqual(self.commit_count(), 2)
        self.assertEqual(
            self.line_count(self.editor_count),
            attempts,
        )

    def test_unrelated_history_refuses_before_execution(self):
        '''
        Treating any advanced `HEAD` as completion can silently skip
        or duplicate work after an unrelated commit. This test
        inserts a commit whose parent is valid but whose tree is not
        the first recorded boundary. The executor must classify it as
        divergence before staging, running checks or opening the
        editor, preserving both the unexpected commit and the pending
        plan for explicit replanning.

        '''
        (self.root / 'other.txt').write_text('other\n')
        self.git('add', 'other.txt')
        self.git('commit', '-q', '-m', 'other')
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('diverged', result.stderr)
        self.assertEqual(self.commit_count(), 2)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_ambient_alternate_index_is_rejected(self):
        '''
        An inherited `GIT_INDEX_FILE` previously redirected every Git
        query and commit away from the user's real worktree index.
        The helper could report success while leaving that index
        stale
        after `HEAD` advanced. This test supplies an alternate-index
        variable during read-only preflight and proves execution
        refuses it before staging, checks, editor invocation or
        commit creation.

        '''
        environment = {
            'GIT_INDEX_FILE': str(self.runtime / 'alternate-index'),
        }
        result = self.invoke(
            '--preflight',
            check=False,
            extra_env=environment,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('ambient Git redirection', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_replacement_ref_does_not_fake_completion(self):
        '''
        Git replacement refs can make an unrelated commit appear to
        have the planned parent and tree. If history classification
        honors that view, the pending boundary is skipped as
        complete. This test replaces an unrelated commit with a
        synthetic planned commit, then proves raw-object
        classification still rejects the real unrelated tree before
        executing any boundary operation.

        '''
        (self.root / 'other.txt').write_text('other\n')
        self.git('add', 'other.txt')
        self.git('commit', '-q', '-m', 'other')
        actual = self.git('rev-parse', 'HEAD').stdout.strip()
        replacement = self.git(
            'commit-tree',
            self.tree_one,
            '-p',
            self.initial_parent,
            '-m',
            'replacement',
        ).stdout.strip()
        self.git('replace', actual, replacement)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('diverged', result.stderr)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_changed_patch_is_rejected_before_staging(self):
        '''
        A plan digest alone does not authenticate a patch reopened by
        a later staging command. Replacing that file could stage
        content outside the reviewed boundary. This test changes the
        role-bound patch after specification generation and proves
        its digest is checked before the real index or any executable
        action changes.

        '''
        original_index = self.git('write-tree').stdout.strip()
        self.patches[0].write_text('changed\n')
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('boundary patch digest changed', result.stderr)
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            original_index,
        )
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_option_shaped_object_id_is_rejected(self):
        '''
        Unvalidated object IDs become options when passed to Git. A
        crafted initial parent could therefore trigger an option side
        effect before normal history validation failed. This test
        pins a new specification containing an option-shaped parent
        and proves canonical-OID validation refuses it before staging
        or creating the option's nominated output file.

        '''
        output = self.runtime / 'injected-output'

        def update(spec):
            spec['initial_parent'] = f'--output={output}'

        self.rewrite_spec(update)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('full canonical OID', result.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(self.commit_count(), 1)

    def test_relative_untracked_executable_is_rejected(self):
        '''
        Preflight formerly resolved a relative executable in the live
        worktree even though execution moved into an exact-tree clone
        where ignored virtual environments and runtime helpers do not
        exist. This test records such an untracked relative
        executable and proves preflight rejects it instead of
        producing a later command-not-found failure after the index
        has been staged.

        '''
        relative = self.relative(self.check_script)

        def update(spec):
            command = spec['boundaries'][0]['project_checks'][0]
            command['argv'][0] = relative

        self.rewrite_spec(update)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'required executable unavailable',
            result.stderr,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            self.initial_tree,
        )

    def test_message_changes_during_checks_use_pinned_snapshot(self):
        '''
        Hashing an archived message before checks is insufficient
        when the final commit reopens its mutable path. A concurrent
        writer could replace reviewed text while preserving the
        planned tree.
        This test makes the project check overwrite the archive after
        authentication and proves the commit still uses the immutable
        byte snapshot read at boundary start.

        '''
        mutator = self.runtime / 'change-message.sh'
        message = self.messages[0]
        mutator.write_text(
            '#!/bin/sh\n'
            f'printf "Changed\\n" > "{message}"\n'
        )
        mutator.chmod(0o755)

        def update(spec):
            spec['boundaries'][0]['project_checks'] = [
                {
                    'argv': [str(mutator)],
                    'env': {},
                    'resolution_argv': ['pwd'],
                },
            ]

        self.rewrite_spec(update)
        self.invoke('--execute', '1')
        subject = self.git('log', '-1', '--format=%s').stdout.strip()
        self.assertEqual(subject, 'Add one')
        self.assertEqual(message.read_text(), 'Changed\n')

    def test_resolution_check_rejects_live_worktree_import(self):
        '''
        An isolated checkout can still import an editable package
        from the live worktree through an external environment.
        Merely clearing common path variables does not prove which
        source was loaded. This test makes the required resolution
        probe report the live package path and proves execution stops
        before project checks, editor invocation or commit creation.

        '''

        def update(spec):
            code = f'print({str(self.root / "fixturepkg.py")!r})'
            check = spec['boundaries'][0]['project_checks'][0]
            check['resolution_argv'] = [sys.executable, '-c', code]

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('escaped the boundary root', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_symlinked_runtime_directory_is_rejected(self):
        '''
        Resolving the canonical runtime before checking containment
        can accept a `msgs` symlink whose target is outside the
        repository. The plan then authenticates externally
        controlled specs, patches and messages as local state. This
        test relocates that directory behind a symlink and proves
        read-only preflight rejects the parent chain without
        executing the plan.

        '''
        messages = self.runtime.parents[0]
        external = Path(self.temp_dir.name) / 'external-messages'
        messages.rename(external)
        messages.symlink_to(external, target_is_directory=True)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('runtime must not use symlinks', result.stderr)
        self.assertEqual(self.commit_count(), 1)

    def test_relative_path_entry_is_rejected(self):
        '''
        A bare executable resolved through a relative `PATH` entry is
        found against the live worktree during preflight but against
        the temporary clone during execution. This test gives the
        resolution probe such a path and proves preflight refuses the
        ambiguous wrapper before staging the boundary.

        '''

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['resolution_argv'][0] = 'python3'
            check['env']['PATH'] = '.:/usr/bin'

        self.rewrite_spec(update)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'required executable unavailable',
            result.stderr,
        )
        self.assertEqual(self.commit_count(), 1)

    def test_fifo_artifact_is_rejected_without_blocking(self):
        '''
        Opening an artifact for a blocking read before checking its
        type lets a writer replace a patch with a FIFO and hang
        preflight indefinitely. This test replaces the first patch
        with a writerless FIFO. The subprocess timeout bounds the
        regression, while the assertions prove the helper reports a
        regular-file error without staging or executing the plan.

        '''
        patch = self.patches[0]
        patch.unlink()
        os.mkfifo(patch)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('must be a regular file', result.stderr)
        self.assertEqual(self.commit_count(), 1)


if __name__ == '__main__':
    unittest.main()
