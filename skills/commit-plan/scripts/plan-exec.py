#!/usr/bin/env python3
'''
Execute generated commit-plan boundaries without duplicate commits.

The generated JSON specification owns commands and immutable
evidence. This helper owns fail-fast execution, exact history
classification and the human-reviewed commit operation.

'''

import argparse
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator


GIT_REDIRECT_VARS = (
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_COMMON_DIR',
    'GIT_DIR',
    'GIT_INDEX_FILE',
    'GIT_NAMESPACE',
    'GIT_OBJECT_DIRECTORY',
    'GIT_WORK_TREE',
)
RUNTIME_PATHS = (
    ('.ai', 'state', 'commit-msg', 'msgs'),
    ('.claude', 'skills', 'commit-msg', 'msgs'),
)


class PlanError(RuntimeError):
    '''
    Report invalid or divergent plan execution safely.

    '''


def visible_text(value: str) -> str:
    '''
    Escape terminal controls while preserving readable text.

    '''
    rendered = []
    for character in value:
        if character.isprintable():
            rendered.append(character)
            continue
        codepoint = ord(character)
        if codepoint <= 0xff:
            rendered.append(f'\\x{codepoint:02x}')
        elif codepoint <= 0xffff:
            rendered.append(f'\\u{codepoint:04x}')
        else:
            rendered.append(f'\\U{codepoint:08x}')
    return ''.join(rendered)


def render_command(arguments: list[str]) -> str:
    '''
    Render one subprocess argv without invoking a shell.

    '''
    safe_arguments = [visible_text(item) for item in arguments]
    return shlex.join(safe_arguments)


def secret_values(
    environment: dict[str, str],
) -> tuple[str, ...]:
    '''
    Return environment values which trace output must redact.

    '''
    values = {
        value
        for value in environment.values()
        if value
    }
    return tuple(sorted(values, key=len, reverse=True))


def append_output(
    lines: list[str],
    label: str,
    payload: str,
    secrets: tuple[str, ...],
) -> None:
    '''
    Append safely rendered captured process output.

    '''
    redacted = payload
    if secrets:
        alternatives = '|'.join(re.escape(item) for item in secrets)
        redacted = re.sub(alternatives, '<redacted>', redacted)
    redacted = redacted.rstrip('\n')
    lines.append(f'{label}:')
    lines.extend(
        f'  {visible_text(item)}'
        for item in redacted.split('\n')
    )


def trace_start(
    phase: str,
    arguments: list[str],
    root: Path,
) -> None:
    '''
    Announce one user-visible executor operation.

    '''
    rendered = render_command(arguments)
    cwd = visible_text(str(root))
    print(
        f'[{phase}] cwd={cwd}\n'
        f'[{phase}] $ {rendered}',
        flush=True,
    )


def trace_result(
    phase: str,
    result: subprocess.CompletedProcess,
    *,
    captured: bool = False,
    secrets: tuple[str, ...] = (),
) -> None:
    '''
    Report one subprocess outcome and captured failure detail.

    '''
    if not result.returncode:
        print(f'[{phase}] PASS', flush=True)
        return
    lines = [f'[{phase}] FAIL exit={result.returncode}']
    if captured and result.stdout:
        append_output(lines, 'stdout', result.stdout, secrets)
    if captured and result.stderr:
        append_output(lines, 'stderr', result.stderr, secrets)
    print('\n'.join(lines), file=sys.stderr, flush=True)


def command_error(
    phase: str,
    arguments: list[str],
    root: Path,
    result: subprocess.CompletedProcess[str],
    *,
    secrets: tuple[str, ...] = (),
) -> PlanError:
    '''
    Build an actionable error for a captured internal command.

    '''
    rendered = render_command(arguments)
    lines = [
        f'[{phase}] FAIL exit={result.returncode}',
        f'cwd: {visible_text(str(root))}',
        f'command: {rendered}',
    ]
    if result.stdout:
        append_output(lines, 'stdout', result.stdout, secrets)
    if result.stderr:
        append_output(lines, 'stderr', result.stderr, secrets)
    return PlanError('\n'.join(lines))


def validation_error(
    phase: str,
    arguments: list[str],
    root: Path,
    reason: str,
    result: subprocess.CompletedProcess[str],
    secrets: tuple[str, ...],
) -> PlanError:
    '''
    Report failed validation after a successful subprocess.

    '''
    rendered = render_command(arguments)
    lines = [
        f'[{phase}] FAIL validation (process exit=0)',
        f'cwd: {visible_text(str(root))}',
        f'command: {rendered}',
        f'reason: {visible_text(reason)}',
    ]
    if result.stdout:
        append_output(lines, 'stdout', result.stdout, secrets)
    if result.stderr:
        append_output(lines, 'stderr', result.stderr, secrets)
    return PlanError('\n'.join(lines))


def git_command(*arguments: str) -> list[str]:
    '''
    Return one raw-object Git command argv.

    '''
    return ['git', *arguments]


def patch_operation() -> tuple[str, ...]:
    '''
    Return the authenticated index transition operation.

    '''
    return (
        'apply',
        '--cached',
        '--binary',
        '--whitespace=nowarn',
        '-',
    )


def structural_operations() -> tuple[tuple[str, ...], ...]:
    '''
    Return the staged boundary inspection operations.

    '''
    return (
        ('diff', '--cached', '--check'),
        ('diff', '--cached', '--stat'),
        ('diff', '--cached', '--name-status'),
    )


def review_operation() -> tuple[str, ...]:
    '''
    Return the mandatory human staged-review operation.

    '''
    return ('diff', '--staged')


def commit_operation(message: str) -> tuple[str, ...]:
    '''
    Return the mandatory editor-backed commit operation.

    '''
    return ('commit', '--edit', '--file', message)


def digest(payload: bytes) -> str:
    '''
    Return the SHA-256 digest for immutable bytes.

    '''
    return hashlib.sha256(payload).hexdigest()


def read_regular(path: Path, label: str) -> bytes:
    '''
    Read one regular non-symlink file through a single descriptor.

    '''
    flags = (
        os.O_RDONLY
        | getattr(os, 'O_NOFOLLOW', 0)
        | getattr(os, 'O_NONBLOCK', 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise PlanError(f'unable to open {label}') from error
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise PlanError(f'{label} must be a regular file')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def git_environment() -> dict[str, str]:
    '''
    Return an environment bound to the real worktree index.

    '''
    redirected = [
        name
        for name in GIT_REDIRECT_VARS
        if os.environ.get(name)
    ]
    if redirected:
        names = ', '.join(redirected)
        raise PlanError(
            f'ambient Git redirection is forbidden: {names}'
        )
    environment = os.environ.copy()
    environment['GIT_NO_REPLACE_OBJECTS'] = '1'
    return environment


def git(
    root: Path,
    *arguments: str,
    check: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    '''
    Run one captured raw-object Git query.

    '''
    active_env = environment or git_environment()
    command_argv = git_command(*arguments)
    cwd = visible_text(str(root))
    try:
        result = subprocess.run(
            command_argv,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env=active_env,
        )
    except OSError as error:
        rendered = render_command(command_argv)
        raise PlanError(
            '[git query] unable to start\n'
            f'cwd: {cwd}\n'
            f'command: {rendered}'
        ) from error
    if check and result.returncode:
        raise command_error(
            'git query',
            command_argv,
            root,
            result,
        )
    return result


def visible_git(
    root: Path,
    phase: str,
    *arguments: str,
) -> int:
    '''
    Run one executor-owned Git command with visible output.

    '''
    command_argv = git_command(*arguments)
    cwd = visible_text(str(root))
    trace_start(phase, command_argv, root)
    try:
        result = subprocess.run(
            command_argv,
            cwd=root,
            check=False,
            env=git_environment(),
        )
    except OSError as error:
        rendered = render_command(command_argv)
        raise PlanError(
            f'[{phase}] unable to start\n'
            f'cwd: {cwd}\n'
            f'command: {rendered}'
        ) from error
    trace_result(phase, result)
    return result.returncode


def required_string(value: Any, field: str) -> str:
    '''
    Validate one required non-empty process-safe string.

    '''
    if not isinstance(value, str) or not value or '\0' in value:
        raise PlanError(f'{field} must be a non-empty safe string')
    return value


def command(value: Any, field: str) -> dict[str, Any]:
    '''
    Validate one project-check command and environment overlay.

    '''
    if not isinstance(value, dict):
        raise PlanError(f'{field} must be a command object')
    argv_value = value.get('argv')
    if not isinstance(argv_value, list) or not argv_value:
        raise PlanError(f'{field}.argv must be a non-empty list')
    argv = [
        required_string(item, f'{field}[{index}]')
        for index, item in enumerate(argv_value)
    ]
    resolution_value = value.get('resolution_argv')
    valid_resolution = (
        isinstance(resolution_value, list)
        and bool(resolution_value)
    )
    if not valid_resolution:
        raise PlanError(
            f'{field}.resolution_argv must be a non-empty list'
        )
    resolution_argv = [
        required_string(item, f'{field}.resolution_argv[{index}]')
        for index, item in enumerate(resolution_value)
    ]
    env_value = value.get('env', {})
    if not isinstance(env_value, dict):
        raise PlanError(f'{field}.env must be an object')
    environment = {}
    forbidden = {
        *GIT_REDIRECT_VARS,
        'AI_SKILLZ_BOUNDARY_ROOT',
        'GIT_NO_REPLACE_OBJECTS',
        'PYTHONHOME',
        'PYTHONPATH',
        '__PYVENV_LAUNCHER__',
    }
    for name, item in env_value.items():
        safe_name = required_string(name, f'{field}.env name')
        if '=' in safe_name:
            raise PlanError(f'{field}.env name contains =')
        if not isinstance(item, str) or '\0' in item:
            raise PlanError(f'{field}.env value is invalid')
        if safe_name in forbidden:
            raise PlanError(f'{field}.env redirects execution')
        environment[safe_name] = item
    return {
        'argv': argv,
        'env': environment,
        'resolution_argv': resolution_argv,
    }


def commands(value: Any, field: str) -> list[dict[str, Any]]:
    '''
    Validate an ordered project-check command sequence.

    '''
    if not isinstance(value, list):
        raise PlanError(f'{field} must be an argv-list sequence')
    return [
        command(item, f'{field}[{index}]')
        for index, item in enumerate(value)
    ]


def artifact(value: Any, field: str) -> dict[str, str]:
    '''
    Validate one role-bound file artifact description.

    '''
    if not isinstance(value, dict):
        raise PlanError(f'{field} must be an object')
    path = required_string(value.get('path'), f'{field}.path')
    checksum = required_string(
        value.get('sha256'),
        f'{field}.sha256',
    )
    if len(checksum) != 64:
        raise PlanError(f'{field}.sha256 must be SHA-256')
    return {'path': path, 'sha256': checksum}


def canonical_root(value: Any) -> Path:
    '''
    Resolve and validate the recorded repository root.

    '''
    raw = required_string(value, 'repo_root')
    try:
        root = Path(raw).resolve(strict=True)
    except OSError as error:
        raise PlanError('repo_root does not exist') from error
    if not root.is_dir():
        raise PlanError('repo_root must be a directory')
    return root


def runtime_root(root: Path, value: Path) -> Path:
    '''
    Resolve the canonical runtime without accepting symlinked
    parents.

    '''
    raw = value if value.is_absolute() else root / value
    lexical = Path(os.path.abspath(raw))
    selected = None
    for parts in RUNTIME_PATHS:
        candidate = root.joinpath(*parts)
        try:
            lexical.relative_to(candidate)
        except ValueError:
            continue
        selected = candidate
        break
    if selected is None:
        raise PlanError('file is outside commit-msg runtime')
    current = root
    for part in selected.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise PlanError(
                'commit-msg runtime must not use symlinks'
            )
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        message = 'commit-msg runtime is missing or outside repo'
        raise PlanError(message) from error
    if not resolved.is_dir():
        raise PlanError('commit-msg runtime must be a directory')
    return resolved


def runtime_file(
    root: Path,
    value: Path,
    label: str,
    runtime: Path | None = None,
) -> Path:
    '''
    Resolve one runtime file without a symlinked directory chain.

    '''
    raw = value if value.is_absolute() else root / value
    lexical = Path(os.path.abspath(raw))
    selected = runtime or runtime_root(root, lexical)
    try:
        relative = lexical.relative_to(selected)
    except ValueError as error:
        raise PlanError(f'{label} is outside commit-msg runtime') \
            from error
    current = selected
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise PlanError(f'{label} parent must not be a symlink')
    try:
        lexical.resolve(strict=True).relative_to(selected)
    except (OSError, ValueError) as error:
        message = f'{label} is missing or outside commit-msg runtime'
        raise PlanError(message) from error
    return lexical


def validate_spec(data: Any) -> dict[str, Any]:
    '''
    Validate the standalone execution specification.

    '''
    if not isinstance(data, dict) or data.get('version') != 1:
        raise PlanError('unsupported plan specification version')
    root = canonical_root(data.get('repo_root'))
    data['repo_root'] = str(root)
    for field in (
        'git_common_dir',
        'git_dir',
        'branch_ref',
        'initial_parent',
        'initial_tree',
        'initial_index_tree',
    ):
        required_string(data.get(field), field)
    boundaries = data.get('boundaries')
    if not isinstance(boundaries, list) or not boundaries:
        raise PlanError('boundaries must be a non-empty list')
    parent_tree = data['initial_tree']
    index_before = data['initial_index_tree']
    for index, boundary in enumerate(boundaries, start=1):
        if not isinstance(boundary, dict):
            raise PlanError(f'boundary {index} must be an object')
        if boundary.get('ordinal') != index:
            raise PlanError('boundary ordinals must be consecutive')
        required_string(boundary.get('subject'), 'subject')
        expected_parent = required_string(
            boundary.get('parent_tree'),
            'parent_tree',
        )
        if expected_parent != parent_tree:
            raise PlanError('boundary parent-tree chain is invalid')
        expected_index = required_string(
            boundary.get('index_before_tree'),
            'index_before_tree',
        )
        if expected_index != index_before:
            raise PlanError('boundary index-tree chain is invalid')
        parent_tree = required_string(boundary.get('tree'), 'tree')
        index_before = parent_tree
        boundary['patch'] = artifact(
            boundary.get('patch'),
            'patch',
        )
        boundary['message'] = artifact(
            boundary.get('message'),
            'message',
        )
        boundary['project_checks'] = commands(
            boundary.get('project_checks'),
            'project_checks',
        )
    return data


def load_spec(path: Path, expected_digest: str) -> dict[str, Any]:
    '''
    Load and authenticate one specification byte snapshot.

    '''
    payload = read_regular(path, 'plan specification')
    if digest(payload) != expected_digest:
        raise PlanError('plan specification digest changed')
    try:
        data = json.loads(payload.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as error:
        message = 'unable to decode plan specification'
        raise PlanError(message) from error
    spec = validate_spec(data)
    root = Path(spec['repo_root'])
    spec_path = runtime_file(root, path, 'plan specification')
    spec['_runtime_root'] = str(runtime_root(root, spec_path))
    return spec


def normalize_git_path(root: Path, value: str) -> str:
    '''
    Normalize a Git metadata path for identity comparison.

    '''
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return str(path.resolve())


def validate_identity(spec: dict[str, Any]) -> Path:
    '''
    Bind execution to the recorded repository, worktree and branch.

    '''
    root = Path(spec['repo_root'])
    actual_root = Path(
        git(root, 'rev-parse', '--show-toplevel').stdout.strip()
    ).resolve()
    if actual_root != root:
        raise PlanError('repository root changed')
    common = git(
        root,
        'rev-parse',
        '--git-common-dir',
    ).stdout.strip()
    git_dir = git(root, 'rev-parse', '--git-dir').stdout.strip()
    if normalize_git_path(root, common) != spec['git_common_dir']:
        raise PlanError('common Git directory changed')
    if normalize_git_path(root, git_dir) != spec['git_dir']:
        raise PlanError('worktree Git directory changed')
    branch = git(root, 'symbolic-ref', '-q', 'HEAD', check=False)
    branch_changed = (
        branch.returncode
        or branch.stdout.strip() != spec['branch_ref']
    )
    if branch_changed:
        raise PlanError('checked-out branch changed')
    validate_objects(spec, root)
    initial_tree = git(
        root,
        'show',
        '-s',
        '--format=%T',
        spec['initial_parent'],
    ).stdout.strip()
    if initial_tree != spec['initial_tree']:
        raise PlanError('initial parent tree changed')
    return root


def validate_objects(spec: dict[str, Any], root: Path) -> None:
    '''
    Validate full canonical object IDs before using them with Git.

    '''
    object_format = git(
        root,
        'rev-parse',
        '--show-object-format',
    ).stdout.strip()
    lengths = {'sha1': 40, 'sha256': 64}
    if object_format not in lengths:
        raise PlanError('unsupported Git object format')
    pattern = re.compile(f'[0-9a-f]{{{lengths[object_format]}}}')
    objects = [
        ('initial_parent', spec['initial_parent'], 'commit'),
        ('initial_tree', spec['initial_tree'], 'tree'),
        (
            'initial_index_tree',
            spec['initial_index_tree'],
            'tree',
        ),
    ]
    for boundary in spec['boundaries']:
        ordinal = boundary['ordinal']
        objects.extend(
            [
                (
                    f'boundary {ordinal} parent_tree',
                    boundary['parent_tree'],
                    'tree',
                ),
                (
                    f'boundary {ordinal} tree',
                    boundary['tree'],
                    'tree',
                ),
                (
                    f'boundary {ordinal} index_before_tree',
                    boundary['index_before_tree'],
                    'tree',
                ),
            ]
        )
    for field, oid, expected_type in objects:
        if pattern.fullmatch(oid) is None:
            raise PlanError(f'{field} must be a full canonical OID')
        actual_type = git(
            root,
            'cat-file',
            '-t',
            oid,
        ).stdout.strip()
        if actual_type != expected_type:
            raise PlanError(f'{field} is not a {expected_type}')


def classify(spec: dict[str, Any], root: Path) -> int:
    '''
    Count the exact completed boundary prefix from raw Git history.

    '''
    initial = spec['initial_parent']
    current = git(root, 'rev-parse', 'HEAD').stdout.strip()
    chain: list[tuple[str, str, str]] = []
    while current != initial:
        if len(chain) >= len(spec['boundaries']):
            raise PlanError(
                'HEAD contains commits outside this plan'
            )
        output = git(
            root,
            'show',
            '-s',
            '--format=%P%x00%T',
            current,
        ).stdout.strip()
        parent_text, separator, tree = output.partition('\0')
        parents = parent_text.split()
        if not separator or len(parents) != 1:
            raise PlanError(
                'plan history is not a single-parent chain'
            )
        chain.append((current, parents[0], tree))
        current = parents[0]
    chain.reverse()
    expected_parent = initial
    for index, (commit_oid, parent_oid, tree) in enumerate(chain):
        expected_tree = spec['boundaries'][index]['tree']
        if parent_oid != expected_parent or tree != expected_tree:
            raise PlanError(
                'HEAD diverged from the planned boundary chain'
            )
        expected_parent = commit_oid
    return len(chain)


def artifact_snapshot(
    spec: dict[str, Any],
    description: dict[str, str],
    role: str,
) -> bytes:
    '''
    Authenticate one role-bound artifact byte snapshot.

    '''
    root = Path(spec['repo_root'])
    raw = Path(description['path'])
    runtime = Path(spec['_runtime_root'])
    path = runtime_file(root, raw, role, runtime)
    payload = read_regular(path, role)
    if digest(payload) != description['sha256']:
        raise PlanError(f'{role} digest changed')
    return payload


def command_executable(
    description: dict[str, Any],
    root: Path,
    tree: str,
    key: str,
) -> bool:
    '''
    Check the directly invoked project executable without running it.

    '''
    value = description[key][0]
    if '/' in value:
        path = Path(value)
        if path.is_absolute():
            is_executable = path.stat().st_mode & 0o111 != 0
            return path.is_file() and is_executable
        if '..' in path.parts:
            return False
        relative = str(path)
        if relative.startswith('./'):
            relative = relative[2:]
        listing = git(
            root,
            'ls-tree',
            tree,
            '--',
            relative,
        ).stdout.strip()
        if not listing:
            return False
        mode = listing.split(maxsplit=1)[0]
        return mode == '100755'
    search_path = description['env'].get(
        'PATH',
        os.environ.get('PATH', ''),
    )
    entries = search_path.split(os.pathsep)
    unsafe_path = any(
        not item or not Path(item).is_absolute()
        for item in entries
    )
    if unsafe_path:
        return False
    return shutil.which(value, path=search_path) is not None


def index_matches(root: Path, tree: str) -> bool:
    '''
    Compare the real index with one tree without changing it.

    '''
    result = git(
        root,
        'diff',
        '--cached',
        '--quiet',
        tree,
        '--',
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise PlanError('unable to compare the staged tree')
    return result.returncode == 0


def apply_patch(root: Path, payload: bytes) -> int:
    '''
    Apply the authenticated boundary patch to the real index.

    '''
    arguments = git_command(*patch_operation())
    cwd = visible_text(str(root))
    trace_start('stage', arguments, root)
    try:
        result = subprocess.run(
            arguments,
            cwd=root,
            check=False,
            input=payload,
            env=git_environment(),
        )
    except OSError as error:
        rendered = render_command(arguments)
        raise PlanError(
            '[stage] unable to start\n'
            f'cwd: {cwd}\n'
            f'command: {rendered}'
        ) from error
    trace_result('stage', result)
    return result.returncode


def isolated_git(
    root: Path,
    environment: dict[str, str],
    *arguments: str,
) -> str:
    '''
    Run one Git command in independent check metadata.

    '''
    command_argv = git_command(*arguments)
    cwd = visible_text(str(root))
    try:
        result = subprocess.run(
            command_argv,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
    except OSError as error:
        rendered = render_command(command_argv)
        raise PlanError(
            '[isolate] unable to start\n'
            f'cwd: {cwd}\n'
            f'command: {rendered}'
        ) from error
    if result.returncode:
        raise command_error(
            'isolate',
            command_argv,
            root,
            result,
        )
    return result.stdout.strip()


@contextlib.contextmanager
def isolated_tree(
    spec: dict[str, Any],
    tree: str,
    parent_oid: str,
) -> Iterator[tuple[Path, dict[str, str]]]:
    '''
    Materialize one tree under independent temporary Git metadata.

    '''
    source_root = Path(spec['repo_root'])
    with tempfile.TemporaryDirectory(
        prefix='commit-plan-check-',
    ) as value:
        root = Path(value) / 'project'
        environment = git_environment()
        environment['GIT_AUTHOR_NAME'] = 'commit-plan'
        environment['GIT_AUTHOR_EMAIL'] = 'commit-plan@invalid'
        environment['GIT_COMMITTER_NAME'] = 'commit-plan'
        environment['GIT_COMMITTER_EMAIL'] = 'commit-plan@invalid'
        environment.pop('PYTHONHOME', None)
        environment.pop('PYTHONPATH', None)
        environment.pop('__PYVENV_LAUNCHER__', None)
        environment['PYTHONNOUSERSITE'] = '1'
        environment['AI_SKILLZ_BOUNDARY_ROOT'] = str(root)
        clone_command = git_command(
            'clone',
            '--shared',
            '--no-checkout',
            '--quiet',
            str(source_root),
            str(root),
        )
        clone_cwd = visible_text(value)
        trace_start('isolate', clone_command, Path(value))
        try:
            result = subprocess.run(
                clone_command,
                cwd=Path(value),
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
        except OSError as error:
            rendered = render_command(clone_command)
            raise PlanError(
                '[isolate] unable to start\n'
                f'cwd: {clone_cwd}\n'
                f'command: {rendered}'
            ) from error
        if result.returncode:
            raise command_error(
                'isolate',
                clone_command,
                Path(value),
                result,
            )
        trace_result('isolate', result)
        isolated_git(root, environment, 'read-tree', tree)
        isolated_git(
            root,
            environment,
            'checkout-index',
            '--all',
            '--force',
        )
        commit_oid = isolated_git(
            root,
            environment,
            'commit-tree',
            tree,
            '-p',
            parent_oid,
            '-m',
            'commit-plan boundary',
        )
        isolated_git(
            root,
            environment,
            'update-ref',
            'refs/heads/plan',
            commit_oid,
        )
        isolated_git(
            root,
            environment,
            'symbolic-ref',
            'HEAD',
            'refs/heads/plan',
        )
        actual_root = isolated_git(
            root,
            environment,
            'rev-parse',
            '--show-toplevel',
        )
        git_dir = isolated_git(
            root,
            environment,
            'rev-parse',
            '--git-dir',
        )
        if Path(actual_root).resolve() != root:
            raise PlanError('isolated check root did not resolve')
        if normalize_git_path(root, git_dir) != str(root / '.git'):
            raise PlanError('isolated Git metadata did not resolve')
        yield root, environment


def run_project_checks(
    spec: dict[str, Any],
    boundary: dict[str, Any],
    parent_oid: str,
) -> int:
    '''
    Run project checks in a fresh exact-tree repository.

    '''
    descriptions = boundary['project_checks']
    if not descriptions:
        return 0
    with isolated_tree(
        spec,
        boundary['tree'],
        parent_oid,
    ) as checked:
        root, environment = checked
        total = len(descriptions)
        for index, description in enumerate(descriptions, start=1):
            check_env = environment.copy()
            check_env.update(description['env'])
            secrets = secret_values(
                check_env,
            )
            resolve_phase = (
                f'project check {index}/{total} resolve'
            )
            resolution = description['resolution_argv']
            cwd = visible_text(str(root))
            trace_start(resolve_phase, resolution, root)
            try:
                probe = subprocess.run(
                    resolution,
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=check_env,
                )
            except OSError as error:
                name = visible_text(
                    description['resolution_argv'][0]
                )
                raise PlanError(
                    f'[{resolve_phase}] unable to start: {name}\n'
                    f'cwd: {cwd}\n'
                    f'command: {render_command(resolution)}'
                ) from error
            if probe.returncode:
                trace_result(
                    resolve_phase,
                    probe,
                    captured=True,
                    secrets=secrets,
                )
                return probe.returncode
            paths = [
                line
                for line in probe.stdout.splitlines()
                if line
            ]
            if not paths:
                raise validation_error(
                    resolve_phase,
                    resolution,
                    root,
                    'resolution check did not print a path',
                    probe,
                    secrets,
                )
            try:
                Path(paths[-1]).resolve(
                    strict=True
                ).relative_to(root)
            except (OSError, ValueError) as error:
                raise validation_error(
                    resolve_phase,
                    resolution,
                    root,
                    'resolution check escaped the boundary root',
                    probe,
                    secrets,
                ) from error
            trace_result(resolve_phase, probe)
            phase = f'project check {index}/{total}'
            arguments = description['argv']
            trace_start(phase, arguments, root)
            try:
                result = subprocess.run(
                    arguments,
                    cwd=root,
                    check=False,
                    env=check_env,
                )
            except OSError as error:
                name = visible_text(description['argv'][0])
                raise PlanError(
                    f'[{phase}] unable to start: {name}\n'
                    f'cwd: {cwd}\n'
                    f'command: {render_command(arguments)}'
                ) from error
            trace_result(phase, result)
            if result.returncode:
                return result.returncode
    return 0


def preflight(spec: dict[str, Any], root: Path) -> None:
    '''
    Validate pending artifacts and executables without executing
    them.

    '''
    completed = classify(spec, root)
    for boundary in spec['boundaries'][completed:]:
        artifact_snapshot(spec, boundary['patch'], 'boundary patch')
        artifact_snapshot(
            spec,
            boundary['message'],
            'commit message',
        )
        for description in boundary['project_checks']:
            for key in ('resolution_argv', 'argv'):
                if not command_executable(
                    description,
                    root,
                    boundary['tree'],
                    key,
                ):
                    name = description[key][0]
                    name = visible_text(name)
                    raise PlanError(
                        f'required executable unavailable: {name}'
                    )


def commit_message(
    root: Path,
    payload: bytes,
) -> tuple[int, str]:
    '''
    Commit the exact index through an editor-backed message snapshot.

    '''
    descriptor, value = tempfile.mkstemp(
        prefix='commit-plan-message-',
        suffix='.md',
    )
    path = Path(value)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        head_before = git(root, 'rev-parse', 'HEAD').stdout.strip()
        operation = commit_operation(str(path))
        result = visible_git(
            root,
            'commit',
            *operation,
        )
        return result, head_before
    finally:
        path.unlink(missing_ok=True)


def execute(
    spec: dict[str, Any],
    root: Path,
    ordinal: int,
) -> int:
    '''
    Execute or safely skip one exact commit boundary.

    '''
    completed = classify(spec, root)
    if ordinal <= completed:
        print(
            f'[boundary {ordinal}] SKIP already complete',
            flush=True,
        )
        return 0
    if ordinal != completed + 1:
        raise PlanError('an earlier boundary is still pending')
    boundary = spec['boundaries'][ordinal - 1]
    subject = visible_text(boundary['subject'])
    print(
        f'[boundary {ordinal}] pending: {subject}',
        flush=True,
    )
    parent_oid = git(root, 'rev-parse', 'HEAD').stdout.strip()
    patch = artifact_snapshot(
        spec,
        boundary['patch'],
        'boundary patch',
    )
    message = artifact_snapshot(
        spec,
        boundary['message'],
        'commit message',
    )
    unmerged = git(root, 'ls-files', '--unmerged').stdout.strip()
    if unmerged:
        raise PlanError('the real index contains unmerged entries')
    target_tree = boundary['tree']
    if not index_matches(root, target_tree):
        before_tree = boundary['index_before_tree']
        if not index_matches(root, before_tree):
            raise PlanError(
                'the real index changed from its planned state'
            )
        result = apply_patch(root, patch)
        if result:
            return result
        if not index_matches(root, target_tree):
            raise PlanError(
                'staging did not produce the boundary tree'
            )
    operations = structural_operations()
    total = len(operations)
    for index, arguments in enumerate(operations, start=1):
        phase = f'structural check {index}/{total}'
        result = visible_git(root, phase, *arguments)
        if result:
            return result
    result = run_project_checks(spec, boundary, parent_oid)
    if result:
        return result
    root = validate_identity(spec)
    if classify(spec, root) != completed:
        raise PlanError('HEAD changed while checks were running')
    if not index_matches(root, target_tree):
        raise PlanError('a check changed the staged tree')
    result = visible_git(root, 'review', *review_operation())
    if result:
        return result
    root = validate_identity(spec)
    if classify(spec, root) != completed:
        raise PlanError('HEAD changed during staged review')
    if not index_matches(root, target_tree):
        raise PlanError('review changed the staged tree')
    result, head_before = commit_message(root, message)
    completed_after = classify(spec, root)
    if completed_after >= ordinal:
        print(f'[boundary {ordinal}] PASS', flush=True)
        return 0
    head_after = git(root, 'rev-parse', 'HEAD').stdout.strip()
    if head_after != head_before:
        raise PlanError(
            'commit changed HEAD outside the planned tree'
        )
    return result or 1


def show(spec: dict[str, Any]) -> None:
    '''
    Print every pinned boundary operation for human review.

    '''
    lines = []
    for boundary in spec['boundaries']:
        if lines:
            lines.append('')
        ordinal = boundary['ordinal']
        subject = visible_text(boundary['subject'])
        patch = visible_text(boundary['patch']['path'])
        lines.extend(
            (
                f'Boundary {ordinal}: {subject}',
                '  Stage:',
                f'    patch: {patch}',
            )
        )
        stage = render_command(git_command(*patch_operation()))
        lines.append(f'    $ {stage} < authenticated patch')
        lines.append('  Structural checks:')
        for operation in structural_operations():
            command_text = render_command(git_command(*operation))
            lines.append(f'    $ {command_text}')
        lines.append('  Project checks:')
        checks = boundary['project_checks']
        if not checks:
            lines.append('    (none)')
        for index, description in enumerate(checks, start=1):
            lines.append(f'    Check {index}/{len(checks)}:')
            lines.append('      cwd: <isolated boundary tree>')
            if description['env']:
                names = ', '.join(
                    visible_text(name)
                    for name in sorted(description['env'])
                )
                lines.append(
                    f'      env: {names} '
                    '(authenticated values hidden)'
                )
            resolution = render_command(
                description['resolution_argv']
            )
            project_check = render_command(description['argv'])
            lines.extend(
                (
                    f'      resolve $ {resolution}',
                    f'      run     $ {project_check}',
                )
            )
        review = render_command(git_command(*review_operation()))
        message = visible_text(boundary['message']['path'])
        commit = render_command(
            git_command(
                *commit_operation('AUTHENTICATED_MESSAGE_SNAPSHOT')
            )
        )
        lines.extend(
            (
                '  Review:',
                f'    $ {review}',
                '  Commit:',
                f'    message: {message}',
                f'    $ {commit}',
            )
        )
    print('\n'.join(lines))


def parse_args(argv: list[str]) -> argparse.Namespace:
    '''
    Parse the standalone plan executor command line.

    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--show', action='store_true')
    mode.add_argument('--execute', type=int, metavar='ORDINAL')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    '''
    Validate, inspect or execute one generated plan specification.

    '''
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        git_environment()
        spec = load_spec(args.spec, args.sha256)
        root = validate_identity(spec)
        if args.preflight:
            preflight(spec, root)
        elif args.show:
            show(spec)
        else:
            if args.execute < 1:
                raise PlanError('boundary ordinal must be positive')
            if args.execute > len(spec['boundaries']):
                raise PlanError(
                    'boundary ordinal is outside the plan'
                )
            return execute(spec, root, args.execute)
    except PlanError as error:
        print(f'commit-plan: {error}', file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        message = f'commit-plan: invalid runtime input: {error}'
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
