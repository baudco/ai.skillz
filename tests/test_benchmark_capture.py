'''
Regress the archived compile/index capture quoting failures.

'''

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
HELPER = HERE / 'benchmark_capture.py'


class CaptureTests(unittest.TestCase):
    '''
    Exercise fixed helper processes with harmless disposable inputs.

    '''

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.serial = 0

    def run_capture(self, request, *, direct=False):
        self.serial += 1
        name = str(self.serial)
        command = [
            sys.executable, '-B', str(HELPER),
            '--cwd', str(self.root), '--output', name,
        ]
        if direct:
            command += ['--', *request['argv']]
        else:
            (self.root / 'request.json').write_text(
                json.dumps(request)
            )
            command += ['--request', 'request.json']
        result = subprocess.run(
            command, cwd=HERE, capture_output=True, timeout=15,
        )
        output = self.root / name
        record = json.loads((output / 'result.json').read_bytes())
        return result, output, record

    def child(self, *args):
        return [sys.executable, '-B', str(Path(__file__)), *args]

    def test_literal_argv_bytes_and_context(self):
        '''
        Nested quote and newline strings broke outer Python -c code.

        Send those literal arguments through JSON and direct argv.
        The fixture reports argv/cwd/env and writes invalid UTF-8;
        exact byte assertions prove capture never decodes child data.
        A secret overlay must be archived but absent from terminal.

        '''
        literal = ['a b', '"nested\'quotes"', 'line\nbreak', '']
        for direct in (False, True):
            request = {
                'argv': self.child('--child', *literal),
                'env': {'CAPTURE_SECRET': 'private value'},
            }
            result, output, record = self.run_capture(
                request, direct=direct,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = (output / 'stdout').read_bytes()
            self.assertTrue(data.endswith(b'\xff\r\n'))
            observed = json.loads(data[:-3])
            self.assertEqual(observed['argv'], literal)
            self.assertEqual(observed['cwd'], str(self.root))
            if not direct:
                self.assertEqual(observed['env'], 'private value')
                self.assertEqual(record['env'], request['env'])
            self.assertEqual(
                (output / 'stderr').read_bytes(), b'\xfe',
            )
            self.assertEqual(record['argv'], request['argv'])
            self.assertNotIn(b'private value', result.stdout)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertGreaterEqual(
                record['monotonic_end_ns'],
                record['monotonic_start_ns'],
            )

    def test_failure_missing_tool_signal_timeout_and_stdin(self):
        '''
        Capture errors must not become successful measurements.

        A fixed child fails, signals itself, waits, or reads stdin.
        Compare actual exit with the raw returncode and status;
        missing argv0 is infrastructure failure, EOF cannot hang, and
        timeout retains prior bytes without waiting on capture pipes.

        '''
        cases = [
            ('--fail', 7, 7, 'completed'),
            ('--signal', 143, -signal.SIGTERM, 'completed'),
            ('--wait', 124, -signal.SIGKILL, 'timeout'),
            ('--stdin', 0, 0, 'completed'),
        ]
        for flag, exit_code, raw, status in cases:
            request = {'argv': self.child(flag)}
            if flag == '--wait':
                request['timeout'] = 0.5
            result, output, record = self.run_capture(request)
            self.assertEqual(result.returncode, exit_code)
            self.assertEqual(record['returncode'], raw)
            self.assertEqual(record['status'], status)
            self.assertEqual((output / 'stdout').read_bytes(), b'ok')
        result, _, record = self.run_capture(
            {'argv': [str(self.root / 'absent')]}
        )
        self.assertEqual(result.returncode, 125)
        self.assertIsNone(record['returncode'])
        self.assertEqual(record['status'], 'infrastructure-error')

    def test_compile_whole_script_without_execution_or_rc(self):
        '''
        The archived compile wrapper failed before reaching Xonsh.

        Compile a full variable/block/continuation script containing
        a write sentinel, then invalid syntax. An rc file also writes
        a sentinel. Neither may execute, and syntax failure must be
        nonzero. Bash receives the same compile-only sentinel check.

        '''
        (self.root / '.xonshrc').write_text(
            "open('rc-ran', 'w').close()\n"
        )
        for shell, source in (
            ('xonsh', "value = 'literal'\nif True:\n"
             "    open('ran', \\\n        'w').close()\n"),
            ('bash', 'touch ran\n'),
        ):
            (self.root / 'plan').write_text(source)
            request = {
                'mode': 'compile', 'shell': shell, 'script': 'plan',
                'env': {
                    'HOME': str(self.root),
                    'XONSHRC': str(self.root / '.xonshrc'),
                    'BASH_ENV': str(self.root / '.xonshrc'),
                },
            }
            result, output, record = self.run_capture(request)
            self.assertEqual(
                result.returncode, 0,
                (output / 'stderr').read_bytes(),
            )
            self.assertEqual(
                (output / 'input.script').read_text(), source,
            )
            self.assertIn('input_sha256', record)
            self.assertFalse((self.root / 'ran').exists())
            self.assertFalse((self.root / 'rc-ran').exists())
            (self.root / 'plan').write_text('if (\n')
            result, _, _ = self.run_capture(request)
            self.assertNotEqual(result.returncode, 0)

    def test_exclusive_output_and_symlink_refusal(self):
        '''
        Retry artifacts must not overwrite the original observation.

        Try an existing archive and a symlink to an unrelated source
        directory. Both must fail before launching the child, keeping
        the original result and source bytes unchanged.

        '''
        request = {'argv': self.child('--stdin')}
        _, output, _ = self.run_capture(request)
        before = (output / 'result.json').read_bytes()
        (self.root / 'link').symlink_to(
            output, target_is_directory=True,
        )
        for name in ('1', 'link'):
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), '--cwd',
                 str(self.root), '--output', name, '--',
                 *self.child('--stdin')], capture_output=True,
            )
            self.assertEqual(result.returncode, 125)
            self.assertEqual(
                (output / 'result.json').read_bytes(), before,
            )

    def test_shared_index_snapshot_and_compare(self):
        '''
        The archived index comparison broke on an escaped newline.

        Query this committed checkout twice using the shared planner
        snapshot, with ambient Git redirection aimed at a missing
        repository.
        Equality includes index bytes/stat and HEAD; changed expected
        HEAD must fail without restoring or staging the actual index.

        '''
        request = {'mode': 'index', 'env': {
            'GIT_DIR': str(self.root / 'missing'),
            'GIT_INDEX_FILE': str(self.root / 'missing-index'),
        }}
        # Only the disposable archive lives under self.root.
        original = self.root
        for name in ('before', 'after', 'changed'):
            request_file = original / 'index-request.json'
            request_file.write_text(json.dumps(request))
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), '--cwd',
                 str(HERE.parent), '--output', str(original / name),
                 '--request', str(request_file)],
                capture_output=True, timeout=15,
            )
            self.assertEqual(
                result.returncode, int(name == 'changed'),
                (original / name / 'stderr').read_bytes(),
            )
            if name == 'before':
                expected = original / name / 'stdout'
                request['expected'] = str(expected)
            elif name == 'after':
                data = json.loads(expected.read_bytes())
                data['head'] = 'changed'
                changed = original / 'expected.json'
                changed.write_text(json.dumps(data))
                request['expected'] = str(changed)


if __name__ == '__main__':
    flag = sys.argv[1] if len(sys.argv) > 1 else ''
    if flag == '--child':
        data = {'argv': sys.argv[2:], 'cwd': os.getcwd(),
                'env': os.environ.get('CAPTURE_SECRET')}
        sys.stdout.buffer.write(
            json.dumps(data).encode() + b'\xff\r\n'
        )
        sys.stderr.buffer.write(b'\xfe')
    elif flag in ('--fail', '--signal', '--wait', '--stdin'):
        os.write(1, b'ok')
        if flag == '--fail':
            sys.exit(7)
        elif flag == '--signal':
            os.kill(os.getpid(), signal.SIGTERM)
        elif flag == '--wait':
            import time
            time.sleep(30)
        else:
            assert sys.stdin.buffer.read() == b''
    else:
        unittest.main()
