#!/usr/bin/env python3
'''
Check the native discovery probe against a deterministic app server.

'''
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from typing import Any
import unittest


def fake_server() -> None:
    '''
    Return controlled skills/list results over the real JSON pipe.

    '''
    case: str = os.environ['TEST_CODEX_CASE']
    root: Path = Path(os.environ['TEST_CODEX_ROOT'])
    line: str
    for line in sys.stdin:
        request: dict[str, Any] = json.loads(line)
        if 'id' not in request:
            continue
        response: dict[str, Any] = {
            'id': request['id'], 'result': {},
        }
        if request['method'] == 'skills/list':
            skill: dict[str, Any] = {
                'name': 'example',
                'scope': 'repo',
                'enabled': case != 'disabled',
                'path': str(root / 'skills/example/SKILL.md'),
            }
            skills: list[dict[str, Any]] = [skill]
            if case == 'missing':
                skills = []
            elif case == 'extra':
                skills.append(dict(
                    skill, name='extra',
                    path=str(root / 'skills/extra/SKILL.md'),
                ))
            elif case == 'path':
                skill['path'] = str(root / 'wrong/SKILL.md')
            response['result'] = {'data': [{
                'errors': ['broken discovery'] if case == 'errors'
                else [],
                'skills': skills,
            }]}
            if case == 'rpc':
                response['error'] = {'message': 'RPC failed'}
        print(json.dumps(response), flush=True)


class DiscoveryProbeTests(unittest.TestCase):
    '''
    Exercise check_loader's public process boundary without Codex.

    '''

    def test_normal_and_optimized_results(self) -> None:
        '''
        Optimization used to erase check_loader's assertions, so an
        empty or invalid skills/list result printed PASS. An isolated
        executable named codex returns each invalid result through
        actual app-server pipes. Fresh normal and -O probe processes
        must reject RPC errors, discovery errors, disabled skills,
        wrong sources, and missing or extra skills without PASS.
        A valid response must still succeed in both modes. Explicit
        unittest checks survive optimization of this runner itself.

        '''
        temp: str
        with tempfile.TemporaryDirectory() as temp:
            root: Path = Path(temp)
            bin_dir: Path = root / 'bin'
            bin_dir.mkdir()
            name: str
            for name in ('example', 'extra'):
                source: Path = root / 'skills' / name
                source.mkdir(parents=True)
                (source / 'SKILL.md').write_text(name)
            executable: Path = bin_dir / 'codex'
            script: str = repr(str(Path(__file__).resolve()))
            executable.write_text(
                f'#!{sys.executable}\n'
                f'import runpy\n'
                f'runpy.run_path({script}, '
                f'run_name="__fake_codex__")\n'
            )
            executable.chmod(0o755)
            env: dict[str, str] = dict(os.environ)
            env.pop('PYTHONOPTIMIZE', None)
            env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
            env['TEST_CODEX_ROOT'] = str(root)
            flags: list[str]
            for flags in ([], ['-O']):
                case: str
                for case in (
                    'valid', 'rpc', 'errors', 'disabled',
                    'path', 'missing', 'extra',
                ):
                    with self.subTest(flags=flags, case=case):
                        env['TEST_CODEX_CASE'] = case
                        result: subprocess.CompletedProcess[str] = (
                            subprocess.run(
                                [sys.executable, *flags, __file__,
                                 '--check'],
                                env=env, text=True,
                                capture_output=True, timeout=40,
                            )
                        )
                        if case == 'valid':
                            self.assertEqual(
                                result.returncode, 0, result.stderr,
                            )
                            self.assertIn('PASS:', result.stdout)
                        else:
                            self.assertNotEqual(
                                result.returncode, 0, result.stdout,
                            )
                            self.assertNotIn('PASS:', result.stdout)


if __name__ == '__fake_codex__':
    fake_server()
elif __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        probe: Path = Path(__file__).with_name('test-codex.py')
        namespace: dict[str, Any] = runpy.run_path(str(probe))
        root: Path = Path(os.environ['TEST_CODEX_ROOT'])
        namespace['check_loader'](
            root, dict(os.environ), {'example'}, root,
        )
    else:
        unittest.main()
