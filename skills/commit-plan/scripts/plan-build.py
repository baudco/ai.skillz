#!/usr/bin/env python3
'''
Prepare boundary evidence, then finalize an executor package.

'''

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


MODULE = importlib.util.spec_from_file_location(
    'plan_exec', Path(__file__).with_name('plan-exec.py')
)
EXEC = importlib.util.module_from_spec(MODULE)
BYTECODE = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    MODULE.loader.exec_module(EXEC)
finally:
    sys.dont_write_bytecode = BYTECODE


def safe_environment():
    '''
    Suppress Git callbacks without changing conversion configuration.

    '''
    environment = EXEC.git_environment()
    parameters = environment.get('GIT_CONFIG_PARAMETERS', '')
    environment['GIT_CONFIG_PARAMETERS'] = (
        (parameters + ' ' if parameters else '')
        + "'core.hooksPath=/dev/null'"
        " 'core.fsmonitor=false'"
    )
    environment['GIT_OPTIONAL_LOCKS'] = '0'
    return environment


def git(root, *arguments, environment=None, check=True, raw=False):
    '''
    Capture Git bytes without newline conversion or callbacks.

    '''
    result = subprocess.run(
        EXEC.git_command(*arguments), cwd=root,
        env=environment or safe_environment(), capture_output=True,
    )
    if check and result.returncode:
        # Do not disclose patch content or filter commands.
        operation = arguments[0]
        status = result.returncode
        raise EXEC.PlanError(
            f'Git {operation} failed (exit={status})'
        )
    if not raw:
        result.stdout = os.fsdecode(result.stdout)
        result.stderr = os.fsdecode(result.stderr)
    return result


def encode(value):
    '''
    Encode deterministic, human-readable JSON evidence.

    '''
    return (json.dumps(value, indent=2) + '\n').encode()


def read_json(path):
    '''
    Read input without following a final-component symlink.

    '''
    return json.loads(EXEC.read_regular(path, 'planner input'))


def store(root, path, payload):
    '''
    Publish complete bytes without replacing an existing artifact.

    '''
    with tempfile.NamedTemporaryFile(dir=path.parent) as stream:
        stream.write(payload)
        stream.flush()
        os.link(stream.name, path)
    return {
        'path': str(path.relative_to(root)),
        'sha256': EXEC.digest(payload),
    }


def snapshot(root):
    '''
    Capture real index bytes, filesystem and stage/debug metadata.

    '''
    value = git(root, 'rev-parse', '--git-path', 'index')
    path = Path(EXEC.normalize_git_path(root, value.stdout.strip()))
    payload = None
    metadata = None
    if path.exists():
        payload = EXEC.read_regular(path, 'real index')
        details = path.stat()
        metadata = [
            details.st_dev,
            details.st_ino,
            details.st_mode,
            details.st_size,
            details.st_mtime_ns,
            details.st_ctime_ns,
        ]
    if git(root, 'ls-files', '--unmerged').stdout:
        raise EXEC.PlanError('unmerged index entries')
    evidence = {
        'sha256': (
            EXEC.digest(payload) if payload is not None else None
        ),
        'stat': metadata,
        'stage_debug': git(
            root, 'ls-files', '--stage', '--debug', '-z'
        ).stdout,
        'staged_paths': git(
            root, 'diff', '--cached', '--name-only', '-z'
        ).stdout,
        'staged_diff': git(
            root,
            'diff',
            '--cached',
            '--binary',
            '--full-index',
            '--no-ext-diff',
            '--no-textconv',
        ).stdout,
        'head': git(root, 'rev-parse', 'HEAD').stdout.strip(),
        'branch': git(
            root, 'symbolic-ref', 'HEAD'
        ).stdout.strip(),
    }
    return evidence, payload


@contextlib.contextmanager
def private_index(root, payload=None):
    '''
    Keep GIT_INDEX_FILE private and remove it on every exit path.

    '''
    git_dir = git(root, 'rev-parse', '--absolute-git-dir')
    with tempfile.TemporaryDirectory(
        prefix='plan-build-', dir=git_dir.stdout.strip()
    ) as directory:
        path = Path(directory) / 'index'
        if payload is not None:
            path.write_bytes(payload)
        environment = safe_environment()
        environment['GIT_INDEX_FILE'] = str(path)
        environment['GIT_LITERAL_PATHSPECS'] = '1'
        yield environment


def materialize(root, recipe, parent, environment):
    '''
    Apply files or a supplied parent-relative patch.

    '''

    def private(*args):
        return git(root, *args, environment=environment).stdout

    private('read-tree', parent)
    if set(recipe) == {'paths'}:
        paths = recipe['paths']
        if not isinstance(paths, list) or not paths:
            raise EXEC.PlanError('paths must be a non-empty list')
        for value in paths:
            EXEC.required_string(value, 'path')
            path = Path(value)
            if (
                path.is_absolute()
                or '..' in path.parts
                or value != path.as_posix()
                or value == '.'
                or '.git' in path.parts
            ):
                raise EXEC.PlanError(
                    'paths must be literal repo files'
                )
            if (root / path).is_dir():
                raise EXEC.PlanError(
                    'directory boundaries unsupported'
                )
            for ancestor in path.parents:
                if (root / ancestor).is_symlink():
                    raise EXEC.PlanError(
                        'selected parent is a symlink'
                    )
        attributes = private(
            'check-attr', '-z', 'filter', '--', *paths,
        ).split('\0')
        configured = git(
            root, 'config', '-z', '--get-regexp',
            r'^filter\..*\.(clean|process)$',
            environment=environment, check=False,
        )
        if configured.returncode not in (0, 1):
            raise EXEC.PlanError('unable to inspect filters')
        for entry in configured.stdout.rstrip('\0').split('\0'):
            key, _, command = entry.partition('\n')
            driver = key[len('filter.'):].rsplit('.', 1)[0]
            if command.strip() and driver in attributes[2::3]:
                raise EXEC.PlanError(
                    'external filter unsupported; supply a patch'
                )
        private('add', '-A', '--', *paths)
        changed = (
            private(
                'diff', '--cached', '--name-only', '-z', parent, '--'
            )
            .rstrip('\0')
            .split('\0')
        )
        if set(changed) - {''} - set(paths):
            raise EXEC.PlanError(
                'selection expands beyond explicit files'
            )
    elif set(recipe) == {'patch'}:
        artifact = recipe['patch']
        payload = EXEC.read_regular(root / artifact['path'], 'patch')
        if EXEC.digest(payload) != artifact['sha256']:
            raise EXEC.PlanError('supplied patch changed')
        private(
            'apply',
            '--cached',
            '--binary',
            '--whitespace=nowarn',
            str(root / artifact['path']),
        )
    else:
        raise EXEC.PlanError('choose exactly one of paths or patch')
    private('diff', '--cached', '--check', parent, '--')
    return private('write-tree').strip()


def prepare(root, request, output, *, strict=False):
    '''
    Freeze explicit boundaries without choosing messages.

    '''
    started = time.perf_counter()
    initial, payload = snapshot(root)
    runtime = EXEC.runtime_root(root, output)
    directory = runtime
    for part in output.parent.relative_to(runtime).parts:
        directory /= part
        if directory.is_symlink() or not directory.is_dir():
            raise EXEC.PlanError(
                'output parent must be a real directory'
            )
    if git(
        root, 'check-ignore', '-q', '--', str(output), check=False
    ).returncode:
        raise EXEC.PlanError('output must be ignored')
    output.mkdir()
    try:
        with private_index(root, payload) as environment:
            initial_index = git(
                root, 'write-tree', environment=environment
            ).stdout.strip()
            parent = git(
                root, 'rev-parse', 'HEAD^{tree}'
            ).stdout.strip()
            spec = {
                'version': 1,
                'repo_root': str(root),
                'branch_ref': initial['branch'],
                'strict_branch': strict,
                'initial_parent': initial['head'],
                'initial_tree': parent,
                'initial_index_tree': initial_index,
                'boundaries': [],
            }
            for field, flag in (
                ('git_dir', '--git-dir'),
                ('git_common_dir', '--git-common-dir'),
            ):
                value = git(
                    root, 'rev-parse', flag
                ).stdout.strip()
                spec[field] = EXEC.normalize_git_path(root, value)
            catalog = {
                key: EXEC.command(value, key)
                for key, value in request.get('checks', {}).items()
            }
            recipes = []
            evidence = []
            boundaries = request['boundaries']
            if not isinstance(boundaries, list) or not boundaries:
                raise EXEC.PlanError('boundaries must be non-empty')
            for ordinal, item in enumerate(boundaries, 1):
                phase = time.perf_counter()
                recipe = {
                    k: v for k, v in item.items() if k != 'checks'
                }
                if 'patch' in recipe:
                    source = Path(recipe['patch'])
                    if not source.is_absolute():
                        source = root / source
                    recipe['patch'] = store(
                        root,
                        output / f'{ordinal:03d}-supplied.patch',
                        EXEC.read_regular(source, 'supplied patch'),
                    )
                tree = materialize(root, recipe, parent, environment)
                if tree == parent:
                    raise EXEC.PlanError('empty boundary')
                before = initial_index if ordinal == 1 else parent

                def diff(left, *flags):
                    return git(
                        root,
                        'diff',
                        '--no-ext-diff',
                        '--no-textconv',
                        '--no-color',
                        '--no-renames',
                        '--src-prefix=a/',
                        '--dst-prefix=b/',
                        *flags,
                        left,
                        tree,
                        '--',
                        raw=True,
                    ).stdout

                changed = set(
                    diff(parent, '--name-only', '-z').split(b'\0')
                )
                transition = set(
                    diff(before, '--name-only', '-z').split(b'\0')
                )
                if payload is not None and not transition <= changed:
                    raise EXEC.PlanError(
                        'transition removes unrelated staged work'
                    )
                patch = store(
                    root,
                    output / f'{ordinal:03d}.patch',
                    diff(before, '--binary', '--full-index'),
                )
                if before != tree:
                    verified = materialize(
                        root, {'patch': patch}, before, environment
                    )
                    if verified != tree:
                        raise EXEC.PlanError(
                            'staging patch tree mismatch'
                        )
                for name, flags in (
                    ('diff', ('--binary', '--full-index')),
                    ('stat', ('--stat',)),
                    ('paths', ('--name-status',)),
                ):
                    evidence.append(
                        store(
                            root,
                            output / f'{ordinal:03d}.{name}',
                            diff(parent, *flags),
                        )
                    )
                spec['boundaries'].append(
                    {
                        'ordinal': ordinal,
                        'parent_tree': parent,
                        'tree': tree,
                        'index_before_tree': before,
                        'patch': patch,
                        'project_checks': [
                            catalog[key]
                            for key in item.get('checks', [])
                        ],
                    }
                )
                recipes.append(recipe)
                parent = tree
                elapsed = time.perf_counter() - phase
                print(
                    f'[prepare boundary {ordinal}] '
                    f'PASS {elapsed:.3f}s',
                    file=sys.stderr,
                    flush=True,
                )
        if snapshot(root)[0] != initial:
            raise EXEC.PlanError('real index or HEAD changed')
        draft = {
            'spec': spec,
            'initial': initial,
            'recipes': recipes,
            'evidence': evidence,
        }
        receipt = store(
            root, output / 'prepared.json', encode(draft)
        )
        elapsed = time.perf_counter() - started
        print(f'[prepare] PASS {elapsed:.3f}s', file=sys.stderr)
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise


def finalize(
    root, prepared, checksum, messages, *,
    render=None, comment_width=69,
):
    '''
    Recheck trees and publish messages plus a pinned v1 spec.

    Optional rendering adds artifact pins and handoff_markdown to
    the returned receipt. The CLI prints that payload after the JSON
    receipt line rather than escaping native commands inside JSON.

    '''
    started = time.perf_counter()
    if render not in (None, 'xonsh', 'bash'):
        raise EXEC.PlanError('--render must be xonsh or bash')
    if type(comment_width) is not int or comment_width < 40:
        raise EXEC.PlanError('--comment-width must be at least 40')
    if render is None and comment_width != 69:
        raise EXEC.PlanError('--comment-width requires --render')
    prepared = EXEC.runtime_file(root, prepared, 'prepared evidence')
    payload = EXEC.read_regular(prepared, 'prepared evidence')
    if EXEC.digest(payload) != checksum:
        raise EXEC.PlanError('prepared evidence digest changed')
    draft = json.loads(payload)
    spec = draft['spec']
    if spec['repo_root'] != str(root):
        raise EXEC.PlanError('prepared repository changed')
    initial, _ = snapshot(root)
    if initial != draft['initial']:
        raise EXEC.PlanError(
            'real index or HEAD drift before finalize'
        )
    boundaries = spec['boundaries']
    if not isinstance(messages, list) or len(messages) != len(
        boundaries
    ):
        raise EXEC.PlanError(
            'one message per prepared boundary required'
        )
    output = prepared.parent / 'final'
    output.mkdir()
    try:
        authenticated = {
            **spec,
            '_runtime_root': str(EXEC.runtime_root(root, prepared)),
        }
        for artifact in draft['evidence']:
            EXEC.artifact_snapshot(
                authenticated, artifact, 'evidence'
            )
        with private_index(root) as environment:
            for boundary, recipe, message in zip(
                boundaries, draft['recipes'], messages, strict=True
            ):
                tree = materialize(
                    root,
                    recipe,
                    boundary['parent_tree'],
                    environment,
                )
                if tree != boundary['tree']:
                    raise EXEC.PlanError(
                        'selected worktree content drift'
                    )
                EXEC.required_string(message, 'message')
                subject = message.splitlines()[0]
                EXEC.required_string(subject, 'message subject')
                ordinal = boundary['ordinal']
                boundary['subject'] = subject
                prefix = prepared.parent.name
                name = f'{prefix}_{ordinal:03d}_commit_msg.md'
                boundary['message'] = store(
                    root, output / name, message.encode()
                )
        EXEC.validate_spec(spec)
        receipt = store(root, output / 'plan.json', encode(spec))
        preflight = subprocess.run(
            [sys.executable, '-B', str(Path(EXEC.__file__)),
             '--spec', str(root / receipt['path']),
             '--sha256', receipt['sha256'], '--preflight'],
            cwd=root, env=safe_environment(), capture_output=True,
        )
        if preflight.returncode:
            raise EXEC.PlanError('executor preflight failed')
        if render is not None:
            # Reuse spec validated above and by child preflight.
            # Runtime-only metadata belongs to a separate copy;
            # never mutate spec after publishing its digest.
            runtime_spec = {
                **spec,
                '_runtime_root': authenticated['_runtime_root'],
            }
            args = argparse.Namespace(
                spec=root / receipt['path'],
                sha256=receipt['sha256'],
                render=render, comment_width=comment_width,
                show=False, strict=False,
            )
            overview = EXEC.overview(runtime_spec) + '\n'
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                EXEC.render(runtime_spec, args)
            commands = stream.getvalue()
            extension = 'xsh' if render == 'xonsh' else 'bash'
            receipt['handoff'] = {
                'shell': render,
                'overview': store(
                    root, output / 'overview.md', overview.encode(),
                ),
                'commands': store(
                    root, output / f'commands.{extension}',
                    commands.encode(),
                ),
            }
            receipt['handoff_markdown'] = (
                f'{overview}\n'
                f'```{extension}\n'
                f'{commands}'
                f'```\n'
            )
        if snapshot(root)[0] != initial:
            raise EXEC.PlanError('real index or HEAD changed')
        store(
            root,
            output / 'verification.json',
            encode(
                {
                    'prepared': {
                        'path': str(prepared),
                        'sha256': checksum,
                    },
                    'real_index_unchanged': True,
                    'selected_trees_unchanged': True,
                    'preflight': 'PASS',
                    'project_checks': 'not run',
                    'initial': initial,
                }
            ),
        )
        elapsed = time.perf_counter() - started
        print(f'[finalize] PASS {elapsed:.3f}s', file=sys.stderr)
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise


def main():
    '''
    Expose two mechanical phases; never execute project checks.

    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    phases = parser.add_subparsers(dest='phase', required=True)
    first = phases.add_parser('prepare')
    first.add_argument('--input', type=Path, required=True)
    first.add_argument('--output', type=Path, required=True)
    first.add_argument(
        '--strict', action='store_true',
        help='require the recorded branch, not only planned history',
    )
    second = phases.add_parser('finalize')
    second.add_argument('--prepared', type=Path, required=True)
    second.add_argument('--sha256', required=True)
    second.add_argument('--messages', type=Path, required=True)
    second.add_argument('--render', choices=('xonsh', 'bash'))
    second.add_argument('--comment-width', type=int, default=69)
    args = parser.parse_args()
    try:
        root = Path(
            git(
                args.repo.resolve(), 'rev-parse', '--show-toplevel'
            ).stdout.strip()
        ).resolve()
        if args.phase == 'prepare':
            result = prepare(
                root, read_json(args.input), args.output.absolute(),
                strict=args.strict,
            )
        else:
            result = finalize(
                root,
                args.prepared,
                args.sha256,
                read_json(args.messages),
                render=args.render, comment_width=args.comment_width,
            )
        handoff = result.pop('handoff_markdown', None)
        receipt = json.dumps(result)
        output = receipt + '\n'
        if handoff is not None:
            output += '\n' + handoff
        print(output, end='')
        return 0
    except (
        EXEC.PlanError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        print(EXEC.visible_text(str(error)), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
