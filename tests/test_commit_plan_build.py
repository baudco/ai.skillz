import importlib.util
import contextlib
import io
import json
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / 'skills/commit-plan/scripts/plan-build.py'
)
MODULE = importlib.util.spec_from_file_location('plan_build', SCRIPT)
BUILD = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(BUILD)


class PlanBuildTests(unittest.TestCase):
    '''
    Exercise mechanical planning in disposable repositories.

    '''

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / '.gitignore').write_text('.ai/state/\n')
        (self.root / 'one').write_text('old\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Base')
        self.runtime = self.root / '.ai/state/commit-msg/msgs'
        self.runtime.mkdir(parents=True)
        self.output = self.runtime / 'fixture'
        (self.root / 'one').write_text('new\n')
        (self.root / 'two').write_text('second\n')
        self.request = {'boundaries': [{'paths': ['one']}]}

    def git(self, *argv):
        return subprocess.run(
            ['git', *argv],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def prepare(self):
        return BUILD.prepare(self.root, self.request, self.output)

    def finalize(self, receipt, messages=None, **options):
        return BUILD.finalize(
            self.root,
            self.root / receipt['path'],
            receipt['sha256'],
            messages or ['Change one\n'],
            **options,
        )

    def assert_cleaned(self):
        self.assertEqual(
            list((self.root / '.git').glob('plan-build-*')), []
        )

    def test_two_boundaries_equivalent_and_read_only(self):
        '''
        Later evidence must exclude earlier boundary changes.

        Select two files separately and compare emitted parent trees
        and patch replay with independent Git tree construction.
        Record subprocesses to prove planning never invokes checks
        or commits, while byte/metadata snapshots prove preservation.

        '''
        self.request['boundaries'].append({'paths': ['two']})
        self.request['checks'] = {
            'never-run': {
                'argv': [sys.executable, '-c', 'raise RuntimeError'],
                'env': {},
                'resolution_argv': [
                    sys.executable, '-c', 'raise RuntimeError',
                ],
            },
        }
        self.request['boundaries'][1]['checks'] = ['never-run']
        before = BUILD.snapshot(self.root)[0]
        live = (self.root / 'one').read_bytes()
        with patch('subprocess.run', wraps=subprocess.run) as run:
            receipt = self.prepare()
            result = self.finalize(receipt, ['One\n', 'Two\n'])
        for call in run.call_args_list:
            argv = call.args[0]
            if argv[0] == 'git':
                self.assertNotEqual(argv[1], 'commit')
            else:
                self.assertEqual(argv[:3], [
                    sys.executable, '-B', str(BUILD.EXEC.__file__),
                ])
                self.assertEqual(argv[-1], '--preflight')
        spec = BUILD.EXEC.load_spec(
            self.root / result['path'], result['sha256']
        )
        BUILD.EXEC.preflight(spec, self.root)
        first, second = spec['boundaries']
        self.assertEqual(second['parent_tree'], first['tree'])
        self.assertEqual(
            self.git(
                'diff', '--name-only', first['tree'], second['tree']
            ),
            'two',
        )
        with BUILD.private_index(self.root) as env:
            BUILD.EXEC.git(
                self.root, 'read-tree', 'HEAD', environment=env
            )
            for boundary, path in zip(
                spec['boundaries'], ['one', 'two'], strict=True
            ):
                BUILD.EXEC.git(
                    self.root, 'add', path, environment=env
                )
                actual = BUILD.EXEC.git(
                    self.root, 'write-tree', environment=env
                ).stdout.strip()
                self.assertEqual(actual, boundary['tree'])
        self.assertEqual(BUILD.snapshot(self.root)[0], before)
        self.assertEqual((self.root / 'one').read_bytes(), live)
        self.assert_cleaned()

    def test_cli_persists_branch_policy(self):
        '''
        New plans need explicit policy, not legacy strict defaults.

        Prepare/finalize through the CLI with and without --strict.
        Inspect each authenticated spec to prove the flag survives
        both phases. Index snapshots prove planning is read-only.

        '''
        request = self.runtime / 'request.json'
        request.write_text(json.dumps(self.request))
        messages = self.runtime / 'messages.json'
        messages.write_text(json.dumps(['Change one\n']))
        initial = BUILD.snapshot(self.root)[0]
        for strict in (False, True):
            with self.subTest(strict=strict):
                output = self.runtime / str(strict)
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT),
                     '--repo', str(self.root), 'prepare',
                     '--input', str(request),
                     '--output', str(output),
                     *(['--strict'] if strict else [])],
                    check=True, capture_output=True, text=True,
                )
                receipt = json.loads(result.stdout)
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT),
                     '--repo', str(self.root), 'finalize',
                     '--prepared', str(self.root / receipt['path']),
                     '--sha256', receipt['sha256'],
                     '--messages', str(messages)],
                    check=True, capture_output=True, text=True,
                )
                final = json.loads(result.stdout)
                spec = BUILD.EXEC.load_spec(
                    self.root / final['path'], final['sha256'],
                )
                self.assertIs(spec['strict_branch'], strict)
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)

    def test_finalize_handoff_native_cli_parity(self):
        '''
        Receipt-only finalize required a dependent render tool round.

        Finalize each frozen fixture first without rendering, then
        remove only its disposable final output and opt into each
        native shell under both persisted branch policies. Identical
        spec bytes/pins prove rendering does not alter frozen inputs.
        Compare stdout and artifact bytes with standalone overview
        and render at that same pin, including non-default width.
        Snapshot equality proves the handoff leaves index/HEAD alone.

        '''
        messages = self.runtime / 'messages.json'
        messages.write_text(json.dumps(['Change `one`\n']))
        initial = BUILD.snapshot(self.root)[0]
        for strict in (False, True):
            for shell in ('xonsh', 'bash'):
                with self.subTest(strict=strict, shell=shell):
                    self.output = self.runtime / f'{strict}-{shell}'
                    prepared = BUILD.prepare(
                        self.root, self.request, self.output,
                        strict=strict,
                    )
                    plain = self.finalize(
                        prepared, ['Change `one`\n'],
                    )
                    spec_path = self.root / plain['path']
                    frozen = spec_path.read_bytes()
                    shutil.rmtree(self.output / 'final')
                    result = subprocess.run(
                        [sys.executable, '-B', str(SCRIPT),
                         '--repo', str(self.root), 'finalize',
                         '--prepared',
                         str(self.root / prepared['path']),
                         '--sha256', prepared['sha256'],
                         '--messages', str(messages),
                         '--render', shell, '--comment-width', '40'],
                        check=True, capture_output=True,
                    )
                    first, handoff = result.stdout.split(b'\n\n', 1)
                    receipt = json.loads(first)
                    self.assertEqual(
                        {key: receipt[key] for key in plain}, plain,
                    )
                    self.assertEqual(spec_path.read_bytes(), frozen)
                    spec = BUILD.EXEC.load_spec(
                        spec_path, receipt['sha256'],
                    )
                    self.assertIs(spec['strict_branch'], strict)
                    native = []
                    for mode in (
                        ['--overview'],
                        ['--render', shell, '--comment-width', '40'],
                    ):
                        native.append(subprocess.run(
                            [sys.executable, '-B',
                             str(BUILD.EXEC.__file__),
                             '--spec', str(spec_path),
                             '--sha256', receipt['sha256'], *mode],
                            check=True, capture_output=True,
                        ).stdout)
                    for key, payload in zip(
                        ('overview', 'commands'), native,
                        strict=True,
                    ):
                        pin = receipt['handoff'][key]
                        self.assertEqual(
                            (self.root / pin['path']).read_bytes(),
                            payload,
                        )
                        self.assertEqual(
                            pin['sha256'],
                            BUILD.EXEC.digest(payload),
                        )
                    fence = b'xsh' if shell == 'xonsh' else b'bash'
                    self.assertEqual(
                        handoff,
                        native[0] + b'\n```' + fence + b'\n'
                        + native[1] + b'```\n',
                    )
                    self.assertEqual(
                        receipt['handoff']['shell'], shell,
                    )
                    with self.assertRaises(FileExistsError):
                        self.finalize(prepared, render=shell)
                    self.assertEqual(spec_path.read_bytes(), frozen)
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assert_cleaned()

    def test_handoff_failure_cleans_unpublished_package(self):
        '''
        Optional rendering must not leave a success-looking package.

        Inject partial renderer stdout then an exception, and a
        separate commands publication error after overview is stored.
        Neither may leak stdout or retain final artifacts. Prepared
        evidence stays byte-identical and can finalize successfully
        after each fault; the real index/HEAD snapshot stays intact.

        '''
        prepared = self.prepare()
        prepared_path = self.root / prepared['path']
        original = prepared_path.read_bytes()
        initial = BUILD.snapshot(self.root)[0]
        store = BUILD.store

        def fail_render(*args):
            '''
            Simulate failure after the renderer starts writing.

            '''
            print('partial render')
            raise ValueError('render failed')

        def fail_store(root, path, payload):
            '''
            Fail commands publication after overview was stored.

            '''
            if path.name == 'commands.xsh':
                raise OSError('publish failed')
            return store(root, path, payload)

        for target, name, replacement in (
            (BUILD.EXEC, 'render', fail_render),
            (BUILD, 'store', fail_store),
        ):
            with self.subTest(failure=name):
                stream = io.StringIO()
                with (
                    patch.object(target, name, replacement),
                    contextlib.redirect_stdout(stream),
                    self.assertRaises((ValueError, OSError)),
                ):
                    self.finalize(prepared, render='xonsh')
                self.assertEqual(stream.getvalue(), '')
                self.assertFalse((self.output / 'final').exists())
                self.assertEqual(
                    prepared_path.read_bytes(), original,
                )
                self.assertEqual(
                    BUILD.snapshot(self.root)[0], initial,
                )
                self.finalize(prepared, render='xonsh')
                shutil.rmtree(self.output / 'final')
        self.assert_cleaned()

    def test_handoff_invalid_options_publish_nothing(self):
        '''
        Bad handoff options must fail before final publication.

        Exercise unsupported shells, too-small/noninteger widths and
        width without render through CLI and callable entry points.
        Empty stdout and absent final output prove no partial receipt
        escaped; unchanged snapshots and a later default call prove
        the same prepared input remains usable by legacy callers.

        '''
        prepared = self.prepare()
        initial = BUILD.snapshot(self.root)[0]
        messages = self.runtime / 'messages.json'
        messages.write_text(json.dumps(['Change one\n']))
        for flags in (
            ['--render', 'fish'],
            ['--render', 'bash', '--comment-width', '39'],
            ['--render', 'xonsh', '--comment-width', 'wide'],
            ['--comment-width', '40'],
        ):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT),
                     '--repo', str(self.root), 'finalize',
                     '--prepared', str(self.root / prepared['path']),
                     '--sha256', prepared['sha256'],
                     '--messages', str(messages), *flags],
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
                self.assertFalse((self.output / 'final').exists())
        for options in (
            {'render': 'fish'},
            {'render': 'bash', 'comment_width': 39},
            {'render': 'xonsh', 'comment_width': 'wide'},
            {'comment_width': 40},
        ):
            with self.assertRaises(BUILD.EXEC.PlanError):
                self.finalize(prepared, **options)
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assertEqual(set(self.finalize(prepared)), {
            'path', 'sha256',
        })

    def test_handoff_retains_evidence_and_drift_refusals(self):
        '''
        Fused rendering must not bypass finalize authentication.

        Corrupt prepared evidence, a reviewed diff and the staging
        patch independently, then introduce worktree, index and HEAD
        drift. Each optional-shell call must refuse and leave no
        final directory. Compare snapshots after each mutation to
        prove refusal preserves rather than restores concurrent work.

        '''
        prepared = self.prepare()
        for name in ('prepared.json', '001.diff', '001.patch'):
            artifact = self.output / name
            original = artifact.read_bytes()
            artifact.write_bytes(b'corrupted')
            for shell in ('xonsh', 'bash'):
                with self.assertRaises(BUILD.EXEC.PlanError):
                    self.finalize(prepared, render=shell)
                self.assertFalse((self.output / 'final').exists())
            artifact.write_bytes(original)
        (self.root / 'one').write_text('drift\n')
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'drift'):
            self.finalize(prepared, render='xonsh')
        (self.root / 'one').write_text('new\n')
        self.git('add', 'two')
        initial = BUILD.snapshot(self.root)[0]
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'drift'):
            self.finalize(prepared, render='bash')
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.output = self.runtime / 'head-drift'
        # Include staged two in the first transition.
        self.request = {'boundaries': [{'paths': ['one', 'two']}]}
        prepared = self.prepare()
        self.git('commit', '-qm', 'Concurrent fixture commit')
        initial = BUILD.snapshot(self.root)[0]
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'drift'):
            self.finalize(prepared, render='xonsh')
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assertFalse((self.output / 'final').exists())
        self.assert_cleaned()

    def test_handoff_only_runs_existing_preflight_child(self):
        '''
        Render fusion must not start a second execution pipeline.

        Select a check and probe that raise if invoked, then record
        every subprocess for both shells. The only Python child must
        be the existing -B preflight with hooks/fsmonitor disabled.
        Any extra check, probe or editor launch fails the argv guard;
        snapshot equality covers index and history preservation.

        '''
        self.request['checks'] = {
            'pending': {
                'argv': [sys.executable, '-c', 'raise RuntimeError'],
                'env': {},
                'resolution_argv': [
                    sys.executable, '-c', 'raise RuntimeError',
                ],
            },
        }
        self.request['boundaries'][0]['checks'] = ['pending']
        initial = BUILD.snapshot(self.root)[0]
        for shell in ('xonsh', 'bash'):
            self.output = self.runtime / shell
            prepared = self.prepare()
            with patch(
                'subprocess.run', wraps=subprocess.run,
            ) as run:
                self.finalize(prepared, render=shell)
            children = []
            for call in run.call_args_list:
                argv = call.args[0]
                if argv[0] == 'git':
                    self.assertNotIn('commit', argv)
                    continue
                children.append(argv)
                self.assertEqual(argv[:3], [
                    sys.executable, '-B', str(BUILD.EXEC.__file__),
                ])
                self.assertEqual(argv[-1], '--preflight')
                config = call.kwargs['env']['GIT_CONFIG_PARAMETERS']
                self.assertIn("'core.hooksPath=/dev/null'", config)
                self.assertIn("'core.fsmonitor=false'", config)
            self.assertEqual(len(children), 1)
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assert_cleaned()

    def test_overlapping_supplied_patch(self):
        '''
        Overlapping edits need explicit parent-relative patches.

        Supply an intermediate edit then select the live final file.
        The second diff must start at intermediate content, not HEAD;
        replay and finalize authenticate both transitions unchanged.

        '''
        supplied = self.runtime / 'input.patch'
        supplied.write_text(
            'diff --git a/one b/one\n'
            '--- a/one\n+++ b/one\n@@ -1 +1 @@\n-old\n+middle\n'
        )
        self.request['boundaries'].insert(
            0, {'patch': str(supplied)}
        )
        receipt = self.prepare()
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'digest'):
            BUILD.finalize(
                self.root, self.root / receipt['path'],
                '0' * 64, ['One\n'],
            )
        diff = (self.output / '002.diff').read_text()
        self.assertIn('-middle\n+new', diff)
        self.finalize(receipt, ['Intermediate\n', 'Final\n'])
        self.assert_cleaned()

    def test_unrelated_staged_refused_without_mutation(self):
        '''
        Transitions must not silently unstage unrelated work.

        Stage the unselected second file before preparing the first.
        Refusal must leave real index bytes and metadata intact,
        removing private indexes and incomplete output artifacts.

        '''
        self.git('add', 'two')
        before = BUILD.snapshot(self.root)[0]
        with self.assertRaisesRegex(
            BUILD.EXEC.PlanError, 'unrelated'
        ):
            self.prepare()
        self.assertEqual(BUILD.snapshot(self.root)[0], before)
        self.assertFalse(self.output.exists())
        self.assert_cleaned()

    def test_drift_integrity_and_no_overwrite(self):
        '''
        Finalization must not bless stale or replaced evidence.

        Change live content after prepare, then restore it and tamper
        with the pinned patch. Both fail without publishing a spec.
        Restore the patch and verify repeated publication refuses
        to overwrite either phase's existing immutable package.

        '''
        receipt = self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        (self.root / 'one').write_text('drift\n')
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'drift'):
            self.finalize(receipt)
        (self.root / 'one').write_text('new\n')
        artifact = self.output / '001.patch'
        original = artifact.read_bytes()
        artifact.write_bytes(b'tampered')
        with self.assertRaises(BUILD.EXEC.PlanError):
            self.finalize(receipt)
        artifact.write_bytes(original)
        self.finalize(receipt)
        with self.assertRaises(FileExistsError):
            self.finalize(receipt)
        self.assert_cleaned()

    def test_missing_index_and_sha256(self):
        '''
        A missing real index must remain absent during planning.

        Rebuild the fixture with SHA-256 object IDs, remove its
        index, then prepare/finalize. Full IDs and absent index state
        must survive; the cached transition starts at the empty tree.

        '''
        with tempfile.TemporaryDirectory() as directory:
            self.root = Path(directory)
            self.git('init', '-q', '--object-format=sha256')
            self.git('config', 'user.name', 'Fixture')
            self.git(
                'config', 'user.email', 'fixture@example.invalid'
            )
            (self.root / '.gitignore').write_text('.ai/state/\n')
            (self.root / 'one').write_text('old\n')
            self.git('add', '.')
            self.git('commit', '-qm', 'Base')
            (self.root / '.git/index').unlink()
            (self.root / 'one').write_text('new\n')
            self.runtime = self.root / '.ai/state/commit-msg/msgs'
            self.runtime.mkdir(parents=True)
            self.output = self.runtime / 'fixture'
            receipt = self.prepare()
            result = self.finalize(receipt)
            spec = json.loads(
                (self.root / result['path']).read_text()
            )
            self.assertEqual(len(spec['initial_parent']), 64)
            self.assertFalse((self.root / '.git/index').exists())
            self.assert_cleaned()

    def test_index_drift_and_failure_cleanup(self):
        '''
        Concurrent staging must block finalize without restoration.

        Stage a file between phases and compare the post-writer index
        before and after refusal. A separate invalid patch exercises
        failure cleanup before any prepared receipt exists.

        '''
        receipt = self.prepare()
        self.git('add', 'two')
        before = BUILD.snapshot(self.root)[0]
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'drift'):
            self.finalize(receipt)
        self.assertEqual(BUILD.snapshot(self.root)[0], before)
        self.output = self.runtime / 'failure'
        bad = self.runtime / 'bad.patch'
        bad.write_text('invalid patch\n')
        self.request = {'boundaries': [{'patch': str(bad)}]}
        with self.assertRaises(BUILD.EXEC.PlanError):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assert_cleaned()

    def test_staged_selection_and_deleted_file(self):
        '''
        Staged selections and deletions need valid transitions.

        Stage the selected edit and delete another tracked file.
        Prepare must retain staged bytes while generating
        a transition containing only the remaining deletion. Finalize
        and executor preflight must accept that exact cached state.

        '''
        self.git('add', 'one')
        (self.root / '.gitignore').unlink()
        self.request['boundaries'][0]['paths'].append('.gitignore')
        # Preserve runtime ignores after deleting .gitignore.
        (self.root / '.git/info/exclude').write_text('.ai/state/\n')
        initial = BUILD.snapshot(self.root)[0]
        self.finalize(self.prepare())
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assertIn(
            'deleted file', (self.output / '001.patch').read_text(),
        )

    def test_unmerged_refused(self):
        '''
        Unmerged stages cannot describe a single initial index tree.

        Install a conflict entry in the fixture's Git index, then
        assert planning refuses before creating a package or private
        index. The original conflict bytes must remain unchanged.

        '''
        oid = self.git('rev-parse', 'HEAD:one')
        zero = '0' * 40
        subprocess.run(
            ['git', 'update-index', '--index-info'],
            input=f'0 {zero}\tone\n100644 {oid} 1\tone\n',
            text=True, check=True, cwd=self.root,
        )
        original = (self.root / '.git/index').read_bytes()
        with self.assertRaisesRegex(
            BUILD.EXEC.PlanError, 'unmerged',
        ):
            self.prepare()
        self.assertEqual(
            (self.root / '.git/index').read_bytes(), original,
        )
        self.assertFalse(self.output.exists())
        self.assert_cleaned()

    def test_callbacks_and_filters_never_run(self):
        '''
        Private indexes previously ran worktree-writing callbacks.

        Install post-index-change and fsmonitor sentinels before both
        phases. Configure clean/process filters that would write the
        same sentinel. Hooks and fsmonitor must stay disabled through
        snapshots and child preflight; filters must refuse before
        staging, including when enabled between prepare and finalize.
        Unset and unspecified attributes must remain supported.

        '''
        callback = self.root / '.git/callback'
        callback.write_text('#!/bin/sh\ntouch callback-ran\n')
        callback.chmod(0o755)
        hooks = self.root / '.git/hooks'
        shutil.copyfile(callback, hooks / 'post-index-change')
        (hooks / 'post-index-change').chmod(0o755)
        self.git('config', 'core.fsmonitor', str(callback))
        self.enterContext(patch.dict(os.environ, {
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'core.hooksPath',
            'GIT_CONFIG_VALUE_0': str(hooks),
            'GIT_CONFIG_PARAMETERS': f"'core.fsmonitor={callback}'",
        }))
        initial = BUILD.snapshot(self.root)[0]
        attrs = self.root / '.gitattributes'
        for conversion in ('clean', 'process'):
            self.git('config', f'filter.evil.{conversion}',
                     str(callback))
        attrs.write_text('* filter=evil\n')
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'filter'):
            self.prepare()
        attrs.write_text('* -filter\n')
        receipt = self.prepare()
        attrs.write_text('* filter=evil\n')
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'filter'):
            self.finalize(receipt)
        attrs.write_text('* !filter\n')
        self.finalize(receipt, render='xonsh')
        self.assertFalse((self.root / 'callback-ran').exists())
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assert_cleaned()

    def test_patch_bytes_and_non_utf8_paths(self):
        '''
        Text-mode Git capture corrupted CRLF and non-UTF8 data.

        Stage a CRLF edit with autocrlf disabled and add ordinary
        non-UTF8 text under a non-UTF8 filename. Both phases must
        preserve exact patch bytes and JSON-escaped stage metadata.
        Blob reads and patch replay prove the emitted tree is exact.

        '''
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'core.whitespace', 'cr-at-eol')
        name = os.fsdecode(b'non-utf8-\xff')
        payloads = {'one': b'crlf\r\n', name: b'text \xff\n'}
        for name, payload in payloads.items():
            (self.root / name).write_bytes(payload)
        self.git('add', 'one')
        self.request['boundaries'][0]['paths'] = list(payloads)
        initial = BUILD.snapshot(self.root)[0]
        receipt = self.prepare()
        result = self.finalize(receipt)
        spec = BUILD.read_json(self.root / result['path'])
        tree = spec['boundaries'][0]['tree']
        for name, payload in payloads.items():
            blob = BUILD.git(
                self.root, 'show', f'{tree}:{name}', raw=True,
            ).stdout
            self.assertEqual(blob, payload)
        diff = (self.output / '001.diff').read_bytes()
        self.assertIn(b'+crlf\r\n', diff)
        self.assertIn(b'+text \xff\n', diff)
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)

    def test_configured_diff_prefixes_are_overridden(self):
        '''
        diff.noprefix produced patches incompatible with apply's -p1.

        Enable both prefix-related settings, prepare and finalize a
        file edit, and inspect the machine patch and full evidence.
        Canonical headers plus exact blob and index comparisons prove
        config cannot change patch replay or the resulting tree.

        '''
        self.git('config', 'diff.noprefix', 'true')
        self.git('config', 'diff.mnemonicPrefix', 'true')
        initial = BUILD.snapshot(self.root)[0]
        result = self.finalize(self.prepare())
        spec = BUILD.read_json(self.root / result['path'])
        tree = spec['boundaries'][0]['tree']
        for name in ('001.patch', '001.diff'):
            payload = (self.output / name).read_bytes()
            self.assertIn(b'diff --git a/one b/one\n', payload)
            self.assertIn(b'--- a/one\n+++ b/one\n', payload)
        self.assertEqual(
            BUILD.git(self.root, 'show', f'{tree}:one',
                      raw=True).stdout,
            b'new\n',
        )
        self.assertEqual(BUILD.snapshot(self.root)[0], initial)
        self.assert_cleaned()

    def test_symlink_parents_refused(self):
        '''
        A runtime parent symlink passed prepare but failed finalize.

        Point a parent symlink inside the runtime and require refusal
        before creating output there. Also select a file through a
        ancestor symlink: attribute inspection and staging
        must not traverse it, even with an in-repository target.

        '''
        (self.runtime / 'real').mkdir()
        (self.runtime / 'link').symlink_to('real')
        self.output = self.runtime / 'link/package'
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'parent'):
            self.prepare()
        self.assertEqual(list((self.runtime / 'real').iterdir()), [])
        (self.root / 'dir').mkdir()
        (self.root / 'dir/file').write_text('content\n')
        (self.root / 'link').symlink_to('dir')
        self.output = self.runtime / 'paths'
        self.request = {'boundaries': [{'paths': ['link/file']}]}
        with self.assertRaisesRegex(BUILD.EXEC.PlanError, 'symlink'):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assert_cleaned()

    def test_deployed_cli_does_not_write_bytecode(self):
        '''
        Loading the adjacent executor mutated deployed source.

        Copy both scripts into a fresh directory with no pycache,
        invoke help and rendered finalize without -B, and compare its
        complete file inventory. Bytecode suppression must restore
        the caller's flag instead of leaking process-global state.

        '''
        deployed = self.root / 'deployed'
        deployed.mkdir()
        for name in ('plan-build.py', 'plan-exec.py'):
            shutil.copyfile(SCRIPT.with_name(name), deployed / name)
        before = sorted(deployed.rglob('*'))
        environment = os.environ.copy()
        environment.pop('PYTHONDONTWRITEBYTECODE', None)
        subprocess.run(
            [sys.executable, str(deployed / SCRIPT.name), '--help'],
            env=environment, check=True, capture_output=True,
        )
        prepared = self.prepare()
        messages = self.runtime / 'messages.json'
        messages.write_text(json.dumps(['Change one\n']))
        subprocess.run(
            [sys.executable, str(deployed / SCRIPT.name),
             '--repo', str(self.root), 'finalize',
             '--prepared', str(self.root / prepared['path']),
             '--sha256', prepared['sha256'],
             '--messages', str(messages), '--render', 'xonsh'],
            env=environment, check=True, capture_output=True,
        )
        self.assertEqual(sorted(deployed.rglob('*')), before)
        module = importlib.util.module_from_spec(MODULE)
        original = sys.dont_write_bytecode
        MODULE.loader.exec_module(module)
        self.assertEqual(sys.dont_write_bytecode, original)


if __name__ == '__main__':
    unittest.main()
