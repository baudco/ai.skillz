#!/usr/bin/env python3
'''
Capture one benchmark observation without shell string assembly.

'''

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def digest(path):
    '''
    Identify the exact reviewed source or captured input bytes.

    '''
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(request, cwd, output):
    '''
    Publish one exclusive archive; never replay or replace results.

    '''
    mode = request.get('mode', 'capture')
    overlay = request.get('env', {})
    if not isinstance(overlay, dict) or not all(
        isinstance(k, str) and k and '=' not in k and '\0' not in k
        and (v is None or isinstance(v, str) and '\0' not in v)
        for k, v in overlay.items()
    ):
        raise ValueError('env must contain string/null values')
    timeout = request.get('timeout')
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout) or timeout <= 0
    ):
        raise ValueError('timeout must be finite and positive')
    overlay = dict(overlay)
    if mode == 'index':
        for key in os.environ.keys() | overlay.keys():
            if key.startswith('GIT_'):
                overlay[key] = None
        overlay.update(
            GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
        )
    if mode == 'compile':
        overlay.update(BASH_ENV=None, ENV=None)
    environment = os.environ.copy()
    for key, value in overlay.items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value
    sources = {str(Path(__file__).resolve()): digest(Path(__file__))}
    payload = None
    if mode == 'capture':
        argv = request.get('argv')
    elif mode == 'compile':
        shell = request.get('shell', 'xonsh')
        if shell not in ('xonsh', 'bash'):
            raise ValueError('compile shell must be xonsh or bash')
        source = cwd / request['script']
        payload = source.read_bytes()
        script = str(output / 'input.script')
        if shell == 'xonsh':
            worker = HERE / 'benchmark_compile.xsh'
            sources[str(worker)] = digest(worker)
            argv = [
                sys.executable, '-B', '-m', 'xonsh', '--no-rc',
                str(worker), script,
            ]
        else:
            argv = ['bash', '--noprofile', '--norc', '-n', script]
    elif mode == 'index':
        worker = HERE / 'benchmark_index.py'
        sources[str(worker)] = digest(worker)
        planner = HERE.parent / 'skills/commit-plan/scripts'
        for name in ('plan-build.py', 'plan-exec.py'):
            sources[str(planner / name)] = digest(planner / name)
        argv = [sys.executable, '-B', str(worker)]
        if 'expected' in request:
            payload = (cwd / request['expected']).read_bytes()
            argv.append(str(output / 'input.script'))
    else:
        raise ValueError('unknown observation mode')
    if not isinstance(argv, list) or not argv or not all(
        isinstance(arg, str) and '\0' not in arg for arg in argv
    ) or not argv[0]:
        raise ValueError('argv must be a non-empty string array')

    # mkdir refuses existing directories and final symlinks alike.
    output.mkdir(mode=0o700)
    record = {
        'version': 1, 'request': request, 'argv': argv,
        'cwd': str(cwd), 'env': overlay, 'sources': sources,
        'python': sys.version, 'returncode': None,
    }
    if payload is not None:
        (output / 'input.script').write_bytes(payload)
        record['input_sha256'] = digest(output / 'input.script')
    record['wall_start_ns'] = time.time_ns()
    record['monotonic_start_ns'] = time.monotonic_ns()
    status = 'completed'
    exit_code = 125
    with (
        (output / 'stdout').open('xb') as stdout,
        (output / 'stderr').open('xb') as stderr,
    ):
        try:
            with subprocess.Popen(
                argv, cwd=cwd, env=environment, shell=False,
                stdin=subprocess.DEVNULL, stdout=stdout,
                stderr=stderr,
            ) as child:
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    status = 'timeout'
                    child.kill()
                    child.wait()
                code = child.returncode
                record['returncode'] = code
                exit_code = 128 - code if code < 0 else code
                if status == 'timeout':
                    exit_code = 124
        except OSError as error:
            status = 'infrastructure-error'
            record['error'] = type(error).__name__
            record['errno'] = error.errno
    record['wall_end_ns'] = time.time_ns()
    record['monotonic_end_ns'] = time.monotonic_ns()
    record['status'] = status
    record['exit_code'] = exit_code
    record['artifacts'] = {
        name: digest(output / name) for name in ('stdout', 'stderr')
    }
    (output / 'result.json').write_text(
        json.dumps(record, indent=2) + '\n'
    )
    # Terminal output intentionally contains no argv/env/child text.
    print(json.dumps({'status': status, 'exit_code': exit_code}))
    return exit_code


def main():
    '''
    Resolve request and artifact paths against the declared cwd.

    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--timeout', type=float)
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cwd = args.cwd.resolve(strict=True)
    if not cwd.is_dir():
        parser.error('cwd must be a directory')
    output = cwd / args.output
    # Resolve only the parent: never follow an existing output link.
    output = output.parent.resolve(strict=True) / output.name
    if args.request:
        if args.argv or args.timeout is not None:
            parser.error('request cannot be mixed with argv/timeout')
        request = json.loads((cwd / args.request).read_bytes())
    else:
        argv = args.argv
        if argv[:1] == ['--']:
            argv = argv[1:]
        request = {'argv': argv, 'timeout': args.timeout}
    try:
        return capture(request, cwd, output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Paths and environment values may contain private data.
        print(type(error).__name__, file=sys.stderr)
        return 125


if __name__ == '__main__':
    sys.exit(main())
