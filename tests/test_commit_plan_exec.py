import hashlib
import json
import os
import pty
import select
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import termios
import time
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
        (self.root / '.gitignore').write_text('/.claude/\n')
        self.git('add', 'base.txt', 'fixturepkg.py', '.gitignore')
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
        shown = self.invoke('--show').stdout
        self.assertIn(
            '$ git commit --edit --file',
            shown,
        )
        self.assertEqual(
            self.git('rev-parse', 'HEAD').stdout.strip(),
            original_head,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            original_index,
        )

        first = self.invoke('--execute', '1')
        self.assertIn(
            '[review] $ git diff --no-ext-diff '
            '--no-textconv --staged',
            first.stdout,
        )
        self.assertIn(
            '[commit] $ git commit --edit --file',
            first.stdout,
        )
        self.assertIn('[boundary 1] PASS', first.stdout)
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

    def test_show_renders_plain_user_commands(self):
        '''
        A JSON operation dump technically exposed project checks,
        review and commit argv but made the commands difficult to
        scan before execution. That obscured the exact tests and
        final human-controlled gates which matter most during review.
        This test renders the fixture plan without executing it and
        compares its text with the same command argv stored in the
        specification. The assertions prove tests, staged review and
        the editor-backed commit are plainly visible while
        environment values remain hidden.

        '''
        shown = self.invoke('--show').stdout
        check = shlex.join(
            [
                str(self.check_script),
                str(self.check_count),
                'one.txt',
                'two.txt',
            ]
        )
        message = self.relative(self.messages[0])
        self.assertIn(f'run     $ {check}', shown)
        self.assertIn(
            '$ git diff --no-ext-diff --no-textconv --staged',
            shown,
        )
        self.assertIn(
            f'message: {message}',
            shown,
        )
        self.assertIn(
            '$ git commit --edit --file '
            'AUTHENTICATED_MESSAGE_SNAPSHOT',
            shown,
        )
        self.assertIn(
            'env: PLAN_TEST_ENV '
            '(authenticated values hidden)',
            shown,
        )
        self.assertNotIn('"project_checks"', shown)

    def test_project_check_failure_reports_command_context(self):
        '''
        A failing project check previously returned only its output
        and exit status, leaving the executor phase, command and
        isolated working directory implicit. This test replaces the
        boundary check with an absolute helper which writes a known
        stderr marker and exits 23 after source resolution succeeds.
        Captured stdout proves the command and temporary cwd were
        announced before execution; stderr proves the phase, status
        and original diagnostic remain visible. The final assertions
        prove failure stops before the editor and commit.

        '''
        failure = self.runtime / 'fail-check.sh'
        failure.write_text(
            '#!/bin/sh\n'
            'printf "trace failure\\n" >&2\n'
            'exit 23\n'
        )
        failure.chmod(0o755)

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [str(failure)]
            check['env'] = {}
            check['resolution_argv'] = ['pwd']

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 23)
        self.assertIn(
            '[project check 1/1] cwd=',
            result.stdout,
        )
        self.assertIn(
            f'[project check 1/1] $ {failure}',
            result.stdout,
        )
        self.assertIn(
            '[project check 1/1] FAIL exit=23',
            result.stderr,
        )
        self.assertIn('trace failure', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_show_escapes_terminal_control_characters(self):
        '''
        Plain command rendering initially passed authenticated
        strings directly to `shlex.join()`, which preserves newlines
        and terminal control bytes. A crafted subject or argument
        could inject a fake commit phase or alter the terminal.
        This test adds newline, carriage-return and ANSI escape bytes
        to previewed fields. Assertions prove they remain visible as
        escaped text on the intended line and cannot create a forged
        command line.

        '''

        def update(spec):
            boundary = spec['boundaries'][0]
            injected = 'safe\n[commit] fake\r\x1b[2J'
            boundary['subject'] = injected
            boundary['project_checks'][0]['argv'].append(injected)

        self.rewrite_spec(update)
        shown = self.invoke('--show').stdout
        self.assertNotIn('\n[commit] fake', shown)
        self.assertNotIn('\r', shown)
        self.assertNotIn('\x1b', shown)
        self.assertIn(r'\x0a[commit] fake\x0d\x1b[2J', shown)

    def test_startup_errors_escape_executable_names(self):
        '''
        Successful previews escape terminal controls, but
        command-not-found errors originally interpolated the
        executable name again. A missing executable containing a
        newline could therefore forge a commit phase during preflight
        or execution. This test records one such resolution command,
        exercises both paths and proves the unsafe bytes appear only
        in escaped form before any project check or editor starts.

        '''
        executable = 'missing\n[commit] fake\x1b[2J'

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['resolution_argv'] = [executable]

        self.rewrite_spec(update)
        for mode in (('--preflight',), ('--execute', '1')):
            result = self.invoke(*mode, check=False)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('\n[commit] fake', output)
            self.assertNotIn('\x1b', output)
            self.assertIn(r'\x0a[commit] fake\x1b[2J', output)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_resolution_failure_redacts_environment_values(self):
        '''
        Resolution probes run with the project check's environment
        and may echo credentials when they fail. Surfacing captured
        stderr verbatim would turn improved diagnostics into a secret
        disclosure. This test makes a failing shell probe print an
        authenticated sentinel from its environment. The trace must
        retain the phase, exit status and stderr section while
        replacing the value, then stop before checks or the editor.

        '''
        explicit_secret = 'authenticated-overlay-value\n'
        inherited_secret = 'inherited-database-value'

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['env'] = {'PLAN_VALUE': explicit_secret}
            check['resolution_argv'] = [
                'sh',
                '-c',
                'printf "%s\\n%s" "$DATABASE_URL" '
                '"$PLAN_VALUE" >&2; exit 19',
            ]

        self.rewrite_spec(update)
        result = self.invoke(
            '--execute',
            '1',
            check=False,
            extra_env={'DATABASE_URL': inherited_secret},
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 19)
        self.assertNotIn(explicit_secret, output)
        self.assertNotIn(inherited_secret, output)
        self.assertIn('<redacted>', result.stderr)
        self.assertIn(
            '[project check 1/1 resolve] FAIL exit=19',
            result.stderr,
        )
        self.assertIn('stderr:', result.stderr)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

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
        self.assertIn(
            '[project check 1/1 resolve] FAIL validation',
            result.stderr,
        )
        self.assertIn('process exit=0', result.stderr)
        self.assertNotIn(
            '[project check 1/1 resolve] PASS',
            result.stdout,
        )
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_relative_resolution_path_uses_isolated_root(self):
        '''
        A valid resolution probe may print a relative module path
        from its isolated checkout. Resolving that output against
        the executor's live cwd used to reject the source as outside
        the boundary, even though the imported module was correct.
        Have the fixture probe import its package and print only the
        module basename. The check, editor and exact-tree commit
        must complete using the isolated root for containment.

        '''

        def update(spec):
            code = (
                'import fixturepkg; from pathlib import Path; '
                'print(Path(fixturepkg.__file__).name)'
            )
            check = spec['boundaries'][0]['project_checks'][0]
            check['resolution_argv'] = [sys.executable, '-c', code]

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1')
        self.assertIn(
            '[project check 1/1 resolve] PASS', result.stdout,
        )
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.line_count(self.check_count), 1)
        self.assertEqual(self.commit_count(), 2)

    def test_probe_rejects_multiple_source_paths(self):
        '''
        Accepting only the final nonempty probe line lets a check
        report an external import followed by a believable in-root
        path. The fixture probe prints both the live worktree copy
        and the actual isolated import path, then exits successfully.
        Execution must refuse that ambiguous evidence before any
        project check, editor or commit despite the valid last line.

        '''
        external = self.root / 'fixturepkg.py'

        def update(spec):
            code = (
                'import pathlib, fixturepkg; '
                f'print({str(external)!r}); '
                'print(pathlib.Path(fixturepkg.__file__).resolve())'
            )
            check = spec['boundaries'][0]['project_checks'][0]
            check['resolution_argv'] = [sys.executable, '-c', code]

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('exactly one path', result.stderr)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)

    def test_absolute_tracked_live_helper_is_refused(self):
        '''
        An absolute executable inside the live repository could run
        edited tracked code absent from the authenticated boundary.
        Make the tracked fixture package executable and replace its
        live bytes with a shell script that would write a marker.
        Both preflight and direct execution must reject that path
        before the helper runs or affects a commit.

        '''
        helper = self.root / 'fixturepkg.py'
        marker = self.runtime / 'tracked-helper-ran'
        helper.write_text(
            '#!/bin/sh\n'
            f'printf "ran\\n" > "{marker}"\n'
        )
        helper.chmod(0o755)

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [str(helper)]

        self.rewrite_spec(update)
        for arguments in (('--preflight',), ('--execute', '1')):
            result = self.invoke(*arguments, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn('required executable unavailable',
                          result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)

    def test_bare_tracked_helper_on_live_path_is_refused(self):
        '''
        Refusing only explicit absolute argv would leave the same
        live tracked helper reachable by a bare executable name
        through the check's PATH overlay. Mark the tracked fixture
        package executable and add the live root to the selected
        PATH. Preflight and direct execution must reject that
        resolved helper before it runs outside the clone.

        '''
        helper = self.root / 'fixturepkg.py'
        helper.chmod(0o755)

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [helper.name]
            check['env']['PATH'] = (
                f'{self.root}{os.pathsep}{os.environ["PATH"]}'
            )

        self.rewrite_spec(update)
        for arguments in (('--preflight',), ('--execute', '1')):
            result = self.invoke(*arguments, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn('required executable unavailable',
                          result.stderr)
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)

    def test_ignored_local_tool_remains_available(self):
        '''
        Repository-local ignored tools such as a virtualenv entry
        point are intentionally external to the commit tree. The
        tracked fixture ignore rule covers the runtime directory.
        Put a check tool there, authenticate its location via
        preflight, then execute the boundary and confirm the tool
        ran with its source path while the imported module came
        from the isolated checkout.

        '''
        helper = self.runtime / 'ignored-check.sh'
        helper.write_text(
            '#!/bin/sh\n'
            f'printf "ran\\n" >> "{self.check_count}"\n'
        )
        helper.chmod(0o755)

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [str(helper)]

        self.rewrite_spec(update)
        self.invoke('--preflight')
        result = self.invoke('--execute', '1')
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.line_count(self.check_count), 1)
        self.assertEqual(self.commit_count(), 2)

    def test_unignored_live_helper_is_refused(self):
        '''
        A live local executable absent from the boundary tree is
        not automatically a trusted external tool. Create an
        untracked, unignored script in the fixture source root and
        pin its absolute path as a project check. Preflight must
        refuse it rather than authorizing mutable code merely
        because the file exists and has executable permissions.

        '''
        helper = self.root / 'unignored-check.sh'
        helper.write_text('#!/bin/sh\nexit 0\n')
        helper.chmod(0o755)

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [str(helper)]

        self.rewrite_spec(update)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'required executable unavailable', result.stderr,
        )
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)

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

    def test_submodule_ignore_cannot_mask_index_divergence(self):
        '''
        Git configuration can hide staged gitlink changes from a
        cached diff. A result of zero would falsely certify the real
        index as the planned tree and permit the wrong commit. Stage
        an extra gitlink in this fixture, enable the ignore setting,
        and verify execution refuses before running checks or editor.

        '''
        self.git('config', 'diff.ignoreSubmodules', 'all')
        self.git(
            'update-index', '--add', '--cacheinfo',
            '160000', self.initial_parent, 'external',
        )
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('real index changed', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)

    def test_project_output_redacted_on_success_and_failure(self):
        '''
        A check inherits environment values, but its raw stdout and
        stderr previously bypassed probe redaction. Exercise both
        exit states with a sentinel in both streams. The successful
        output remains visible without disclosing the value, while
        failure stops before the commit with the same protection.

        '''
        secret = 'very-private-check-secret'

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [
                'sh', '-c',
                'printf "%s" "$PLAN_SECRET"; '
                'printf "%s" "$PLAN_SECRET" >&2; '
                'exit "$CHECK_EXIT"',
            ]
            check['resolution_argv'] = ['pwd']
            check['env'] = {'PLAN_SECRET': secret, 'CHECK_EXIT': '0'}

        self.rewrite_spec(update)
        success = self.invoke('--execute', '1')
        self.assertNotIn(secret, success.stdout + success.stderr)
        self.assertIn('<redacted>', success.stdout)
        self.assertIn('stdout:', success.stdout)
        self.assertIn('stderr:', success.stdout)
        self.assertIn('[boundary 1] PASS', success.stdout)

        def fail(spec):
            check = spec['boundaries'][1]['project_checks'][0]
            check['argv'] = [
                'sh', '-c',
                'printf "%s" "$PLAN_SECRET"; '
                'printf "%s" "$PLAN_SECRET" >&2; exit 27',
            ]
            check['resolution_argv'] = ['pwd']
            check['env'] = {'PLAN_SECRET': secret}

        self.rewrite_spec(fail)
        failure = self.invoke('--execute', '2', check=False)
        self.assertEqual(failure.returncode, 27)
        self.assertNotIn(secret, failure.stdout + failure.stderr)
        self.assertIn('<redacted>', failure.stderr)
        self.assertEqual(self.commit_count(), 2)

    def test_checks_cannot_change_the_tree_under_test(self):
        '''
        A successful check can edit tracked source inside the shared
        isolated clone. Without a post-check comparison, the next
        check observes that edited source and passes on content not
        present in the planned commit. Mutate the clone from a first
        command and verify execution stops before a second check,
        review, or commit while the live source remains unchanged.

        '''
        mutation = self.runtime / 'mutate-clone.sh'
        mutation.write_text(
            '#!/bin/sh\n'
            'printf "VALUE = 42\\n" > fixturepkg.py\n'
        )
        mutation.chmod(0o755)

        def update(spec):
            first = spec['boundaries'][0]['project_checks'][0]
            first['argv'] = [str(mutation)]
            spec['boundaries'][0]['project_checks'].append(
                first.copy()
            )

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('changed the isolated tree', result.stderr)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(
            (self.root / 'fixturepkg.py').read_text(),
            'VALUE = "live"\n',
        )

    def test_later_boundary_completion_is_not_accepted(self):
        '''
        A hook may advance its isolated commit checkout through a
        later planned tree. The executor must reject that checkout
        before publishing any unexpected commit on the live branch.

        '''
        hook = self.root / '.git' / 'hooks' / 'post-commit'
        hook.write_text(
            '#!/bin/sh\n'
            f'target=$(git commit-tree {self.tree_two} '
            '-p HEAD -m unexpected) || exit 1\n'
            'git update-ref HEAD "$target"\n'
        )
        hook.chmod(0o755)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('private commit changed', result.stderr)
        self.assertNotIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.commit_count(), 1)

    def test_early_pager_exit_does_not_abort_review(self):
        '''
        Git used to stream a staged diff directly into the pager.
        Pressing q before the diff was fully written could send
        SIGPIPE to Git and block an otherwise reviewed commit.
        Configure an early-exiting pager during a noninteractive
        invocation. The executor must not start a pager without a
        terminal, show the sanitized diff directly, and reach the
        editor without handing Git output to the external command.

        '''
        pager = 'head -c 1 >/dev/null'
        result = self.invoke(
            '--execute', '1',
            extra_env={'GIT_PAGER': pager},
        )
        self.assertIn('diff --git a/one.txt', result.stdout)
        self.assertIn('[review] PASS', result.stdout)
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.line_count(self.editor_count), 1)

    def test_noninteractive_pager_is_not_executed(self):
        '''
        A configured external pager could print credentials or
        terminal controls, bypassing diff sanitization. Supply a
        pager command that writes a marker and fails if launched.
        Without an interactive terminal, the executor must not
        run it. The sanitized review and fixture editor-backed
        commit still complete normally.

        '''
        marker = self.runtime / 'pager-ran'
        marker_arg = shlex.quote(str(marker))
        pager = f'printf marker > {marker_arg}; exit 17'
        result = self.invoke(
            '--execute', '1',
            extra_env={'GIT_PAGER': pager},
        )
        self.assertFalse(marker.exists())
        self.assertIn('[review] PASS', result.stdout)
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.commit_count(), 2)

    def test_concurrent_staging_cannot_join_the_commit(self):
        '''
        A writer previously could stage an unrelated path after the
        last review comparison while the editor was open. The real
        index lock must reject that writer, and the private commit
        index must contain only the authenticated boundary tree.
        An editor stub tries to stage with `GIT_INDEX_FILE` removed,
        then allows the commit; the exact commit tree, reconciled
        real index and remaining untracked file prove isolation.

        '''
        marker = self.runtime / 'writer-refused'
        editor = self.runtime / 'race-editor.sh'
        editor.write_text(
            '#!/bin/sh\n'
            f'printf "unrelated\\n" > "{self.root}/unrelated.txt"\n'
            'env -u GIT_INDEX_FILE -u GIT_DIR '
            '-u GIT_WORK_TREE -u GIT_COMMON_DIR '
            f'git -C "{self.root}" add -- unrelated.txt '
            '2>/dev/null && exit 41\n'
            f'printf "refused\\n" > "{marker}"\n'
        )
        editor.chmod(0o755)
        self.editor_script = editor
        result = self.invoke('--execute', '1')
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(marker.read_text(), 'refused\n')
        self.assertEqual(
            self.git('rev-parse', 'HEAD^{tree}').stdout.strip(),
            self.tree_one,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            self.tree_one,
        )
        self.assertEqual(
            (self.root / 'unrelated.txt').read_text(),
            'unrelated\n',
        )
        self.assertFalse((self.root / '.git/index.lock').exists())

    def test_index_changing_hook_retains_recovery_evidence(self):
        '''
        User hooks run against the private commit index. A hook that
        deliberately stages another file can change the tree Git
        commits. This fixture stages an extra path from pre-commit;
        the executor must not publish or call it PASS and must retain
        the isolated checkout for explicit recovery.

        '''
        hook = self.root / '.git' / 'hooks' / 'pre-commit'
        hook.write_text(
            '#!/bin/sh\n'
            'printf "hook\\n" > unexpected.txt\n'
            'git add -- unexpected.txt\n'
        )
        hook.chmod(0o755)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('private commit changed', result.stderr)
        self.assertIn('commit checkout retained', result.stderr)
        self.assertEqual(
            self.git('write-tree').stdout.strip(),
            self.tree_one,
        )
        self.assertFalse((self.root / '.git/index.lock').exists())

    def test_configured_hook_output_is_trusted(self):
        '''
        Capturing Git output escaped hook controls but also denied
        interactive editors their terminal. The commit boundary
        explicitly trusts locally configured hooks. A fixture hook
        emits ESC to both inherited streams: its raw output must be
        distinguished from sanitized automated Git diagnostics,
        and the boundary must still finish successfully.

        '''
        hook = self.root / '.git' / 'hooks' / 'pre-commit'
        hook.write_text(
            '#!/bin/sh\n'
            "printf '\\033[31mhook\\033[0m\\n'\n"
            "printf '\\033[32merror\\033[0m\\n' >&2\n"
        )
        hook.chmod(0o755)
        result = self.invoke('--execute', '1')
        self.assertIn('\x1b', result.stdout + result.stderr)
        self.assertIn('[boundary 1] PASS', result.stdout)

    def run_pty_review(
        self,
        editor: Path,
        pager: str | None,
        *,
        no_pager: bool = False,
    ) -> tuple[str, int, bool, bool]:
        '''
        Drive the fixture's pager and review gate in a real PTY.

        '''
        arguments = [
            sys.executable, str(SCRIPT), '--spec',
            str(self.spec_path), '--sha256',
            self.spec_digest, '--execute', '1',
        ]
        if no_pager:
            arguments.append('--no-pager')
        environment = os.environ.copy()
        environment['GIT_EDITOR'] = str(editor)
        if pager is None:
            environment.pop('GIT_PAGER', None)
        else:
            environment['GIT_PAGER'] = pager
        environment['PYTHONPATH'] = str(self.root)
        pid, master = pty.fork()
        if pid == 0:
            os.chdir(self.root)
            os.execve(sys.executable, arguments, environment)
        chunks = []
        finished = 0
        status = 0
        pager_closed = False
        confirmed = False
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                ready, _, _ = select.select(
                    [master], [], [], 0.1,
                )
                if ready:
                    try:
                        output = os.read(master, 65536)
                    except OSError:
                        output = b''
                    if output:
                        chunks.append(output)
                    transcript = b''.join(chunks)
                    if (
                        not no_pager
                        and not pager_closed
                        and b'diff --git a/one.txt' in transcript
                    ):
                        os.write(master, b'q')
                        pager_closed = True
                    if (
                        not confirmed
                        and b'Review the staged diff above'
                        in transcript
                    ):
                        os.write(master, b'\n')
                        confirmed = True
                finished, status = os.waitpid(pid, os.WNOHANG)
                if finished:
                    break
            if not finished:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                self.fail('interactive fixture never finished')
        finally:
            os.close(master)
        text = b''.join(chunks).decode(errors='backslashreplace')
        return (
            text,
            os.waitstatus_to_exitcode(status),
            pager_closed,
            confirmed,
        )

    def test_review_and_editor_use_a_real_terminal(self):
        '''
        Capturing commit output fed pipes to Vim or nano and broke
        their required terminal interaction. Restored paging must
        not erase the explicit human review gate. Run the fixture
        executor in a PTY with a repo-configured pager wrapping
        real `less`. Send q after the diff, then Enter. An editor
        requiring terminal stdio and `/dev/tty` proves the pager
        exit did not replace the editor-backed commit review.

        '''
        pager = shutil.which('less')
        if pager is None:
            self.skipTest('less is unavailable')
        selected = self.runtime / 'selected-pager'
        configured = self.runtime / 'configured-pager.sh'
        configured.write_text(
            '#!/bin/sh\n'
            f'printf "selected\\n" > "{selected}"\n'
            f'exec {shlex.quote(pager)} -RX "$@"\n'
        )
        configured.chmod(0o755)
        self.git('config', 'pager.diff', str(configured))
        marker = self.runtime / 'editor-had-tty'
        editor = self.runtime / 'tty-editor.sh'
        editor.write_text(
            '#!/bin/sh\n'
            '[ -t 0 ] && [ -t 1 ] && [ -t 2 ] || exit 47\n'
            ': </dev/tty || exit 48\n'
            f'printf "yes\\n" > "{marker}"\n'
        )
        editor.chmod(0o755)
        text, status, pager_closed, confirmed = self.run_pty_review(
            editor, None,
        )
        self.assertEqual(status, 0)
        self.assertEqual(selected.read_text(), 'selected\n')
        self.assertTrue(pager_closed)
        self.assertTrue(confirmed)
        self.assertIn('Review the staged diff above', text)
        self.assertEqual(marker.read_text(), 'yes\n')
        self.assertEqual(self.commit_count(), 2)

    def test_no_pager_opt_out_keeps_review_gate(self):
        '''
        A user can opt out of a configured pager without losing the
        sanitized direct diff or Enter-before-editor gate. Supply a
        malicious-looking pager which writes a fixture marker if
        launched. Run `--no-pager` in a real PTY and confirm it never
        executes that command, yet the user review and editor finish.

        '''
        marker = self.runtime / 'pager-ran'
        editor = self.editor_script
        marker_arg = shlex.quote(str(marker))
        pager = f'printf yes > {marker_arg}; exit 17'
        text, status, pager_closed, confirmed = self.run_pty_review(
            editor, pager, no_pager=True,
        )
        self.assertEqual(status, 0)
        self.assertFalse(marker.exists())
        self.assertFalse(pager_closed)
        self.assertTrue(confirmed)
        self.assertIn('diff --git a/one.txt', text)
        self.assertEqual(self.commit_count(), 2)

    def test_interactive_pager_failure_blocks_commit(self):
        '''
        Trusting a human-configured pager must not mistake its own
        failed exit for a reviewed diff. A fixture pager returns 17
        without displaying the sanitized input in a real PTY. The
        review gate must stop before confirmation, editor or commit
        and leave the planned boundary staged for another attempt.

        '''
        text, status, pager_closed, confirmed = self.run_pty_review(
            self.editor_script, 'exit 17',
        )
        self.assertEqual(status, 17)
        self.assertFalse(pager_closed)
        self.assertFalse(confirmed)
        self.assertIn('[review] FAIL exit=17', text)
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )

    def test_pager_interrupt_restores_tty_before_shell_prompt(self):
        '''
        A pager can be killed by Ctrl-C before it restores its raw
        terminal mode. Returning to Xonsh in that mode lets a late
        cursor-position reply appear as shell input and delays its
        prompt. Launch a pager which intentionally disables canonical
        input and echo, then send Ctrl-C and a cursor reply through a
        real PTY. The executor must abort without opening the editor,
        preserve the staged boundary, restore the terminal mode and
        discard the stray cursor reply before the shell resumes.

        '''
        pager = self.runtime / 'raw-pager.py'
        pager.write_text(
            'import os, signal, termios\n'
            "fd = os.open('/dev/tty', os.O_RDWR)\n"
            'mode = termios.tcgetattr(fd)\n'
            'mode[3] &= ~(termios.ICANON | termios.ECHO)\n'
            'termios.tcsetattr(fd, termios.TCSANOW, mode)\n'
            "os.write(1, b'PAGER_READY\\n\\x1b[6n')\n"
            'signal.signal(signal.SIGINT, signal.SIG_DFL)\n'
            'signal.pause()\n'
        )
        environment = os.environ.copy()
        executable = shlex.quote(sys.executable)
        script = shlex.quote(str(pager))
        environment['GIT_PAGER'] = f'{executable} -u {script}'
        environment['GIT_EDITOR'] = str(self.editor_script)
        environment['PYTHONPATH'] = str(self.root)
        environment['NO_COLOR'] = '1'
        arguments = [
            sys.executable, str(SCRIPT), '--spec',
            str(self.spec_path), '--sha256',
            self.spec_digest, '--execute', '1',
        ]
        pid, master = pty.fork()
        if pid == 0:
            os.chdir(self.root)
            os.execve(sys.executable, arguments, environment)
        slave = os.open(
            os.ptsname(master),
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY,
        )
        before = termios.tcgetattr(master)
        chunks = []
        finished = 0
        status = 0
        interrupted = False
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                ready, _, _ = select.select(
                    [master], [], [], 0.1,
                )
                if ready:
                    try:
                        output = os.read(master, 65536)
                    except OSError:
                        output = b''
                    chunks.append(output)
                    if not interrupted and b'PAGER_READY' in (
                        b''.join(chunks)
                    ):
                        os.write(master, b'\x03\x1b[59;1R')
                        interrupted = True
                finished, status = os.waitpid(pid, os.WNOHANG)
                if finished:
                    break
            if not finished:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                self.fail('interrupted pager never finished')
            self.assertTrue(interrupted)
            self.assertEqual(os.waitstatus_to_exitcode(status), 130)
            self.assertEqual(self.line_count(self.editor_count), 0)
            self.assertEqual(self.commit_count(), 1)
            self.assertEqual(
                self.git('write-tree').stdout.strip(), self.tree_one,
            )
            self.assertEqual(
                termios.tcgetattr(master)[3]
                & (termios.ICANON | termios.ECHO),
                before[3] & (termios.ICANON | termios.ECHO),
            )
            with self.assertRaises(BlockingIOError):
                os.read(slave, 128)
        finally:
            os.close(slave)
            os.close(master)

    def test_no_pager_flag_requires_execution(self):
        '''
        A review-pager opt-out has meaning only when executing a
        pending boundary. Applying it to display-only preflight or
        show could make users assume those modes reviewed a patch.
        Both invalid invocations must refuse without staging,
        checks, editor interaction or a commit.

        '''
        for mode in ('--preflight', '--show'):
            result = self.invoke(mode, '--no-pager', check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn(
                '--no-pager requires --execute', result.stderr,
            )
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_direct_review_escapes_staged_controls(self):
        '''
        Spooling a diff prevents pager SIGPIPE but copying its bytes
        unchanged still emits malicious file content to the terminal.
        Build a planned tree whose added file contains ESC, execute
        without a pager, and verify review displays escaped controls
        without losing the line break or blocking the commit.

        '''
        (self.root / 'one.txt').write_text('one\x1b[31m\n')
        self.tree_one = self.index_tree('one.txt')
        self.tree_two = self.index_tree('one.txt', 'two.txt')
        self.patches = [
            self.make_patch(
                'one.patch', self.initial_tree, self.tree_one,
            ),
            self.make_patch(
                'two.patch', self.tree_one, self.tree_two,
            ),
        ]
        self.write_spec()
        result = self.invoke('--execute', '1')
        self.assertNotIn('\x1b', result.stdout)
        self.assertIn('\\x1b[31m', result.stdout)
        self.assertIn('[boundary 1] PASS', result.stdout)

    def test_noninteractive_pager_cannot_bypass_diff_escaping(self):
        '''
        Git once passed staged diff text to a configured pager that
        could output its own unsanitized controls. Materialize a
        planned file containing ESC and configure an external pager;
        without a terminal the executor must emit the escaped diff
        directly before an otherwise successful fixture commit.

        '''
        (self.root / 'one.txt').write_text('one\x1b[31m\n')
        self.tree_one = self.index_tree('one.txt')
        self.tree_two = self.index_tree('one.txt', 'two.txt')
        self.patches = [
            self.make_patch(
                'one.patch', self.initial_tree, self.tree_one,
            ),
            self.make_patch(
                'two.patch', self.tree_one, self.tree_two,
            ),
        ]
        self.write_spec()
        result = self.invoke(
            '--execute', '1', extra_env={'GIT_PAGER': 'cat'},
        )
        self.assertNotIn('\x1b', result.stdout)
        self.assertIn('\\x1b[31m', result.stdout)
        self.assertIn('[boundary 1] PASS', result.stdout)

    def test_graft_does_not_fake_completed_boundary(self):
        '''
        A local graft can rewrite the parent shown by `git show`
        even with replacement refs disabled. An unrelated commit
        with the planned tree and a real extra parent therefore used
        to appear complete. Forge that view in the fixture graft
        file, then require raw-object classification to refuse the
        actual history before checks, staging or editor invocation.

        '''
        intermediate = self.git(
            'commit-tree', self.initial_tree,
            '-p', self.initial_parent, '-m', 'intermediate',
        ).stdout.strip()
        other = self.git(
            'commit-tree', self.tree_one,
            '-p', intermediate, '-m', 'unrelated',
        ).stdout.strip()
        self.git('update-ref', 'HEAD', other)
        grafts = self.root / '.git' / 'info' / 'grafts'
        grafts.write_text(f'{other} {self.initial_parent}\n')
        apparent = self.git(
            'show', '-s', '--format=%P', other,
        ).stdout.strip()
        self.assertEqual(apparent, self.initial_parent)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('diverged', result.stderr)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_untracked_check_outputs_do_not_cross_clones(self):
        '''
        Checks ran in separate processes but shared one checkout.
        The first check could leave an untracked module for a later
        check to import, so the latter tested state outside the
        authenticated tree. Make the first check create a file and
        the second fail if it exists. Both pass only if each has a
        fresh exact-tree clone, without losing their required order.

        '''

        def update(spec):
            checks = spec['boundaries'][0]['project_checks']
            checks[0]['argv'] = [
                'sh', '-c', 'printf "generated\\n" > generated.txt',
            ]
            checks[0]['resolution_argv'] = ['pwd']
            checks.append({
                'argv': [
                    'sh', '-c', 'test ! -e generated.txt',
                ],
                'resolution_argv': ['pwd'],
                'env': {},
            })

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1')
        self.assertEqual(result.stdout.count('[isolate] PASS'), 2)
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.commit_count(), 2)

    def test_stage_diagnostics_escape_terminal_controls(self):
        '''
        Patch application previously inherited stdout and stderr.
        A failing Git command could print control bytes from patch
        context directly to the terminal while the executor claimed
        to escape diagnostics. A fixture Git shim delegates all
        other queries but emits ESC and fails for `git apply`.
        Execution must report its staged phase and exit status with
        escaped text, without running checks, editor or commit.

        '''
        tools = self.runtime / 'bin'
        tools.mkdir()
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        shim = tools / 'git'
        shim.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = apply ]; then\n'
            "  printf '\\033[31mstage failed\\033[0m\\n' >&2\n"
            '  exit 23\n'
            'fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o755)
        path = f'{tools}{os.pathsep}{os.environ["PATH"]}'
        result = self.invoke(
            '--execute', '1', check=False,
            extra_env={'PATH': path},
        )
        self.assertEqual(result.returncode, 23)
        self.assertNotIn('\x1b', result.stdout + result.stderr)
        self.assertIn('\\x1b', result.stderr)
        self.assertIn('[stage] FAIL exit=23', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_failed_commit_cannot_claim_hook_advanced_head(self):
        '''
        A pre-commit hook can create the expected boundary commit
        and update HEAD, then exit nonzero. An equality check on
        history alone previously called this failed `git commit`
        successful and reconciled the private index. The hook here
        creates exactly the expected tree before exiting 17. The
        executor must report failure, preserve recovery evidence,
        and leave the staged real index and lock state intact.

        '''
        hook = self.root / '.git' / 'hooks' / 'pre-commit'
        hook.write_text(
            '#!/bin/sh\n'
            f'target=$(git commit-tree {self.tree_one} '
            f'-p {self.initial_parent} -m hook) || exit 1\n'
            'git update-ref HEAD "$target" || exit 1\n'
            'exit 17\n'
        )
        hook.chmod(0o755)
        result = self.invoke('--execute', '1', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('[commit] FAIL', result.stderr)
        self.assertIn('commit checkout retained', result.stderr)
        self.assertNotIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )
        self.assertFalse((self.root / '.git/index.lock').exists())

    def test_non_utf8_check_failure_keeps_phase_and_output(self):
        '''
        Capturing project-check output with strict text decoding
        previously raised UnicodeDecodeError for arbitrary bytes.
        The executor then lost the check's phase, status and error
        output behind a generic runtime-input failure. A fixture
        check emits invalid UTF-8 to both streams and exits 23;
        escaped diagnostics must remain visible before commit.

        '''

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [
                'sh', '-c',
                "printf '\\377\\n'; "
                "printf '\\376\\n' >&2; exit 23",
            ]
            check['resolution_argv'] = ['pwd']

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 23)
        self.assertIn(
            '[project check 1/1] FAIL exit=23', result.stderr,
        )
        self.assertIn('\\xff', result.stderr)
        self.assertIn('\\xfe', result.stderr)
        self.assertNotIn('invalid runtime input', result.stderr)
        self.assertEqual(self.commit_count(), 1)

    def test_isolated_check_cannot_rewrite_its_head(self):
        '''
        A probe or check can move the isolated clone's HEAD and
        worktree to another exact tree. Comparing the clone against
        its mutable HEAD would then approve a check that no longer
        ran against the authenticated boundary. Reset a fixture
        clone to its parent and exit successfully; the executor must
        reject the moved ref before staged review or commit.

        '''

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [
                'git', 'reset', '--hard', 'HEAD^',
            ]
            check['resolution_argv'] = ['pwd']

        self.rewrite_spec(update)
        result = self.invoke('--execute', '1', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('changed the isolated HEAD', result.stderr)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_missing_executable_name_is_escaped(self):
        '''
        An absolute executable with a newline or ESC can fail at
        `Path.stat()` before the ordinary preflight error renders
        its name. With a raw exception path, a hostile plan could
        inject terminal controls. Point a pending check at a missing
        file containing both controls, then require escaped output
        and no project check, editor or commit execution.

        '''
        absent = self.runtime / 'missing\n\x1b[31m'

        def update(spec):
            check = spec['boundaries'][0]['project_checks'][0]
            check['argv'] = [str(absent)]

        self.rewrite_spec(update)
        result = self.invoke('--preflight', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('\x1b', result.stdout + result.stderr)
        self.assertNotIn('\n\x1b', result.stdout + result.stderr)
        self.assertIn('\\x1b', result.stderr)
        self.assertIn(
            'required executable unavailable', result.stderr,
        )
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)
        self.assertEqual(self.commit_count(), 1)

    def test_special_real_index_is_rejected_without_blocking(self):
        '''
        Git commands inspecting the real index can block on a FIFO
        before the executor checks its index type. A symlink or
        directory can likewise redirect or invalidate that input.
        Replace the fixture index with each special type and invoke
        both preflight and execution under a bounded subprocess
        timeout. Each must refuse before Git opens it or stages a
        boundary, and the fixture index is restored afterward.

        '''
        index = self.root / '.git' / 'index'
        original = index.read_bytes()
        external = self.runtime / 'external-index'
        external.write_bytes(original)
        for kind in ('fifo', 'symlink', 'directory'):
            with self.subTest(kind=kind):
                index.unlink()
                if kind == 'fifo':
                    os.mkfifo(index)
                elif kind == 'symlink':
                    index.symlink_to(external)
                else:
                    index.mkdir()
                try:
                    for arguments in (
                        ('--preflight',),
                        ('--execute', '1'),
                    ):
                        result = self.invoke(
                            *arguments, check=False,
                        )
                        self.assertEqual(result.returncode, 2)
                        self.assertIn(
                            'Git index is not a regular file',
                            result.stderr,
                        )
                finally:
                    if kind == 'directory':
                        index.rmdir()
                    else:
                        index.unlink()
                    index.write_bytes(original)
        self.assertEqual(self.commit_count(), 1)
        self.assertEqual(self.line_count(self.check_count), 0)
        self.assertEqual(self.line_count(self.editor_count), 0)

    def test_absent_index_stages_nonempty_boundary(self):
        '''
        An absent real index represents the empty tree even when
        HEAD contains tracked files. Pin the first boundary's patch
        against that empty tree, remove the fixture's real index,
        and execute it. The executor must create the exact target
        index under its lock before review and commit; this path
        must keep working while handling an empty target too.

        '''
        empty = self.git(
            'hash-object', '-w', '-t', 'tree', '/dev/null',
        ).stdout.strip()
        patch = self.make_patch(
            'absent-index.patch', empty, self.tree_one,
        )

        def update(spec):
            spec['initial_index_tree'] = empty
            boundary = spec['boundaries'][0]
            boundary['index_before_tree'] = empty
            boundary['patch'] = {
                'path': self.relative(patch),
                'sha256': self.digest(patch),
            }

        self.rewrite_spec(update)
        index = self.root / '.git' / 'index'
        index.unlink()
        self.invoke('--preflight')
        result = self.invoke('--execute', '1')
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertTrue(index.is_file())
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )
        self.assertEqual(self.commit_count(), 2)

    def test_absent_index_materializes_empty_target(self):
        '''
        `git diff --cached` treats a missing index as the empty
        tree, so an empty target previously skipped staging and
        reached the commit lock without a real index. Make a plan
        to delete all tracked files from a nonempty HEAD, with an
        empty initial index, target and patch. Removing the index
        reproduces the skip; execution must publish an empty index
        under its lock, review the deletion, and commit exactly once.

        '''
        empty = self.git(
            'hash-object', '-w', '-t', 'tree', '/dev/null',
        ).stdout.strip()
        patch = self.make_patch('empty-target.patch', empty, empty)

        def update(spec):
            spec['initial_index_tree'] = empty
            spec['boundaries'] = spec['boundaries'][:1]
            boundary = spec['boundaries'][0]
            boundary['tree'] = empty
            boundary['index_before_tree'] = empty
            boundary['project_checks'] = []
            boundary['patch'] = {
                'path': self.relative(patch),
                'sha256': self.digest(patch),
            }

        self.rewrite_spec(update)
        index = self.root / '.git' / 'index'
        index.unlink()
        self.invoke('--preflight')
        result = self.invoke('--execute', '1')
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertTrue(index.is_file())
        self.assertEqual(
            self.git('write-tree').stdout.strip(), empty,
        )
        self.assertEqual(self.commit_count(), 2)
        self.assertEqual(self.line_count(self.editor_count), 1)
        self.assertEqual(self.line_count(self.check_count), 0)

    def test_external_diff_and_textconv_never_run(self):
        '''
        Git can load `GIT_EXTERNAL_DIFF` and an attribute-selected
        textconv driver from local configuration. An executor-owned
        diff must not run either program while comparing the index,
        checking structure, or showing the human the planned patch.
        First prove both fixture drivers run for ordinary Git diff,
        then execute the same boundary and require no driver marker.

        '''
        external_marker = self.runtime / 'external-ran'
        external = self.runtime / 'external.sh'
        external.write_text(
            '#!/bin/sh\n'
            f'printf "ran\\n" > "{external_marker}"\n'
        )
        external.chmod(0o755)
        textconv_marker = self.runtime / 'textconv-ran'
        textconv = self.runtime / 'textconv.sh'
        textconv.write_text(
            '#!/bin/sh\n'
            f'printf "ran\\n" > "{textconv_marker}"\n'
        )
        textconv.chmod(0o755)
        (self.root / '.git/info/attributes').write_text(
            'one.txt diff=external\n'
        )
        self.git('config', 'diff.external.textconv', str(textconv))
        self.git('add', '--', 'one.txt')
        environment = os.environ.copy()
        environment['GIT_EXTERNAL_DIFF'] = str(external)
        self.run_process(
            ['git', 'diff', '--staged'], env=environment,
        )
        self.assertTrue(external_marker.exists())
        external_marker.unlink()
        self.run_process(
            ['git', 'diff', '--staged', '--textconv'],
        )
        self.assertTrue(textconv_marker.exists())
        textconv_marker.unlink()
        self.git('read-tree', 'HEAD')

        result = self.invoke(
            '--execute', '1',
            extra_env={'GIT_EXTERNAL_DIFF': str(external)},
        )
        self.assertFalse(external_marker.exists())
        self.assertFalse(textconv_marker.exists())
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(self.commit_count(), 2)

    def test_staging_lock_excludes_a_concurrent_writer(self):
        '''
        Staging validation and patch application used separate real
        index operations. An external Git writer between them could
        alter the index before the patch applied. A Git shim attempts
        to stage an unrelated file when the patch begins; the writer
        must hit the real index lock, while the planned patch and
        subsequent editor-backed commit finish without that file.

        '''
        tools = self.runtime / 'staging-bin'
        tools.mkdir()
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        marker = self.runtime / 'stage-writer-refused'
        shim = tools / 'git'
        shim.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = apply ]; then\n'
            f'  printf "other\\n" > "{self.root}/other.txt"\n'
            '  env -u GIT_INDEX_FILE -u GIT_DIR '
            '-u GIT_WORK_TREE -u GIT_COMMON_DIR '
            f'  {shlex.quote(real_git)} -C "{self.root}" '
            'add -- other.txt 2>/dev/null && exit 41\n'
            f'  printf "refused\\n" > "{marker}"\n'
            'fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o755)
        path = f'{tools}{os.pathsep}{os.environ["PATH"]}'
        result = self.invoke(
            '--execute', '1', extra_env={'PATH': path},
        )
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(marker.read_text(), 'refused\n')
        self.assertEqual(
            self.git('rev-parse', 'HEAD^{tree}').stdout.strip(),
            self.tree_one,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )
        self.assertEqual(
            (self.root / 'other.txt').read_text(), 'other\n',
        )

    def test_ref_cas_refuses_race_after_private_commit(self):
        '''
        The live branch can move after the detached editor-backed
        commit succeeds. A Git shim moves the real branch to a
        different valid commit just before publication. The expected
        old-parent CAS must fail, keep that writer's commit, and
        retain the detached checkout instead of publishing an
        unexpected-parent plan commit or overwriting the real index.
        The shim publishes from the detached checkout to model a
        second worktree, independent of this one's HEAD lock.

        '''
        concurrent = self.git(
            'commit-tree', self.initial_tree,
            '-p', self.initial_parent, '-m', 'concurrent',
        ).stdout.strip()
        branch = self.git('symbolic-ref', 'HEAD').stdout.strip()
        tools = self.runtime / 'ref-bin'
        tools.mkdir()
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        shim = tools / 'git'
        shim.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = update-ref '
            f'] && [ "$2" = "{branch}" ]; then\n'
            f'  {shlex.quote(real_git)} '
            f'update-ref "{branch}" {concurrent} '
            f'{self.initial_parent} || exit 23\n'
            'fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o755)
        path = f'{tools}{os.pathsep}{os.environ["PATH"]}'
        result = self.invoke(
            '--execute', '1', check=False,
            extra_env={'PATH': path},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'branch changed during publication', result.stderr,
        )
        self.assertIn('commit checkout retained', result.stderr)
        self.assertEqual(
            self.git('rev-parse', 'HEAD').stdout.strip(), concurrent,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )
        self.assertNotIn('[boundary 1] PASS', result.stdout)

    def test_late_ref_change_cannot_reconcile_another_tree(self):
        '''
        An old reconciliation read `HEAD` after classifying a
        successful commit. A concurrent ref move in that gap could
        replace the real index with another user's tree and still
        print PASS. Move the real ref when the executor checks its
        private index after CAS. It must fail with the live staged
        tree intact, rather than reading or copying mutable HEAD.

        '''
        concurrent = self.git(
            'commit-tree', self.initial_tree,
            '-p', self.initial_parent, '-m', 'concurrent',
        ).stdout.strip()
        branch = self.git('symbolic-ref', 'HEAD').stdout.strip()
        tools = self.runtime / 'late-ref-bin'
        tools.mkdir()
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        shim = tools / 'git'
        shim.write_text(
            '#!/bin/sh\n'
            'case "$1:$GIT_INDEX_FILE" in\n'
            '  write-tree:*commit-plan-index-*)\n'
            f'    current=$({shlex.quote(real_git)} '
            f'-C "{self.root}" rev-parse HEAD) || exit 23\n'
            f'    {shlex.quote(real_git)} -C "{self.root}" '
            f'update-ref "{branch}" {concurrent} '
            '"$current" || exit 23\n'
            '    ;;\n'
            'esac\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o755)
        path = f'{tools}{os.pathsep}{os.environ["PATH"]}'
        result = self.invoke(
            '--execute', '1', check=False,
            extra_env={'PATH': path},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'branch changed after publication', result.stderr,
        )
        self.assertEqual(
            self.git('rev-parse', 'HEAD').stdout.strip(), concurrent,
        )
        self.assertEqual(
            self.git('write-tree').stdout.strip(), self.tree_one,
        )
        self.assertNotIn('[boundary 1] PASS', result.stdout)

    def test_branch_switch_during_publication_is_refused(self):
        '''
        A concurrent `git symbolic-ref HEAD` could switch this
        worktree to a different branch at the same parent between
        identity checks and publication. Publishing through a
        mutable branch name would then commit the plan on the wrong
        branch. Create a second branch and inject that switch from
        the Git command just before CAS. The source HEAD lock must
        refuse it while publication reaches only the pinned branch.

        '''
        branch = self.git('symbolic-ref', 'HEAD').stdout.strip()
        other = 'refs/heads/other'
        self.git('branch', 'other', self.initial_parent)
        tools = self.runtime / 'branch-switch-bin'
        tools.mkdir()
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        marker = self.runtime / 'switch-refused'
        shim = tools / 'git'
        shim.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = update-ref '
            f'] && [ "$2" = "{branch}" ]; then\n'
            '  env -u GIT_INDEX_FILE -u GIT_DIR '
            '-u GIT_WORK_TREE -u GIT_COMMON_DIR '
            f'{shlex.quote(real_git)} -C "{self.root}" '
            f'symbolic-ref HEAD "{other}" '
            '2>/dev/null && exit 41\n'
            f'  printf "refused\\n" > "{marker}"\n'
            'fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o755)
        path = f'{tools}{os.pathsep}{os.environ["PATH"]}'
        result = self.invoke(
            '--execute', '1', extra_env={'PATH': path},
        )
        self.assertIn('[boundary 1] PASS', result.stdout)
        self.assertEqual(marker.read_text(), 'refused\n')
        self.assertEqual(
            self.git('symbolic-ref', 'HEAD').stdout.strip(), branch,
        )
        self.assertEqual(
            self.git('rev-parse', other).stdout.strip(),
            self.initial_parent,
        )
        self.assertEqual(
            self.git('rev-parse', 'HEAD^{tree}').stdout.strip(),
            self.tree_one,
        )
        self.assertFalse((self.root / '.git/HEAD.lock').exists())


if __name__ == '__main__':
    unittest.main()
