#!/usr/bin/env python3
'''
Resolve and explicitly migrate repository-owned workflow state.

Discovery links never own mutable data. Preview is read-only;
application preserves legacy originals and never touches Git's index.

'''

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


# key: (legacy location, neutral location)
PATHS: dict[str, tuple[str, str]] = {
    'commit_messages': (
        '.claude/skills/commit-msg/msgs',
        '.ai/state/commit-msg/msgs',
    ),
    'commit_latest': (
        '.claude/git_commit_msg_LATEST.md',
        '.ai/state/commit-msg/LATEST.md',
    ),
    'pr_messages': (
        '.claude/skills/pr-msg/msgs',
        '.ai/state/pr-msg/msgs',
    ),
    'pr_latest': (
        '.claude/skills/pr-msg/pr_msg_LATEST.md',
        '.ai/state/pr-msg/LATEST.md',
    ),
    'review_context': (
        '.claude/review_context.md',
        '.ai/state/review/context.md',
    ),
    'review_regression': (
        '.claude/review_regression.md',
        '.ai/state/review/regression.md',
    ),
    'review_replies': (
        '.claude/review_replies',
        '.ai/state/review/replies',
    ),
    'commit_style': (
        '.claude/skills/commit-msg/style-guide-reference.md',
        '.ai/commit-msg/style-guide-reference.md',
    ),
    'test_harness': (
        '.claude/skills/run-tests/test-harness-reference.md',
        '.ai/run-tests/test-harness-reference.md',
    ),
    'commit_config': (
        '.claude/skills/commit-msg/conf.toml',
        '.ai/commit-msg/conf.toml',
    ),
    'pr_config': (
        '.claude/skills/pr-msg/conf.toml',
        '.ai/pr-msg/conf.toml',
    ),
}
GUIDANCE: set[str] = {'commit_style', 'test_harness'}
MARKER: str = '.ai/workflow-state.json'
RECEIPT: str = '.ai/state/migrations/workflow-state.json'
IGNORE: str = '''# BEGIN ai.skillz: workflow-state
/.ai/state/
/.ai/commit-msg/conf.toml
/.ai/pr-msg/conf.toml
# END ai.skillz: workflow-state
'''


def digest(data: bytes) -> str:
    '''
    Hash file bytes without exposing their contents.

    '''
    return hashlib.sha256(data).hexdigest()


def safe(root: Path, relative: str) -> Path:
    '''
    Reject symlinks and paths outside the active worktree.

    '''
    if Path(relative).is_absolute():
        raise ValueError(f'Absolute path is forbidden: {relative}')
    path: Path = root
    part: str
    parts: tuple[str, ...] = Path(relative).parts
    for part in parts:
        if part in ('..', '.'):
            raise ValueError(f'Unsafe path: {relative}')
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlink requires review: {relative}')
        if (
            path != root / relative
            and
            path.exists()
            and
            not path.is_dir()
        ):
            raise ValueError(
                f'Parent is not a directory: {relative}'
            )
    return path


def files(root: Path, relative: str) -> dict[str, str]:
    '''
    Inventory regular files beneath a managed path.

    '''
    path: Path = safe(root, relative)
    if not path.exists():
        return {}
    if path.is_file():
        return {relative: digest(path.read_bytes())}
    if not path.is_dir():
        raise ValueError(f'Unsupported file type: {relative}')
    result: dict[str, str] = {}
    child: Path
    for child in sorted(path.iterdir()):
        result.update(files(root, str(child.relative_to(root))))
    return result


def inspect(root: Path) -> dict[str, Any]:
    '''
    Resolve one backend and report conflicting payloads.

    '''
    marker: Path = safe(root, MARKER)
    selected: str | None = None
    if marker.exists():
        config: dict[str, Any] = json.loads(marker.read_text())
        if not isinstance(config, dict):
            raise ValueError('Invalid workflow-state configuration')
        if config.get('version') != 1:
            raise ValueError('Unsupported workflow-state version')
        selected = config.get('backend')
        if selected not in ('legacy', 'neutral'):
            raise ValueError('Invalid workflow-state backend')
    legacy: dict[str, str] = {}
    neutral: dict[str, str] = {}
    key: str
    pair: tuple[str, str]
    for key, pair in PATHS.items():
        legacy.update(files(root, pair[0]))
        neutral.update(files(root, pair[1]))
    extra: Path
    for extra in sorted(
        (root / '.claude').glob('git_commit_msg_*.md')
    ):
        legacy.update(files(root, str(extra.relative_to(root))))
    backend: str = selected or ('legacy' if legacy else 'neutral')
    blockers: list[str] = []
    if selected is None and legacy and neutral:
        blockers.append(
            'Both layouts contain data; preview migration'
        )
    resolved: dict[str, str] = {}
    for key, pair in PATHS.items():
        resolved[key] = pair[0 if backend == 'legacy' else 1]
        if key in GUIDANCE:
            if (root / pair[1]).exists():
                resolved[key] = pair[1]
            if (
                backend != 'neutral'
                and (root / pair[0]).exists()
                and (root / pair[1]).exists()
                and (root / pair[0]).read_bytes()
                != (root / pair[1]).read_bytes()
            ):
                blockers.append(f'Divergent guidance: {key}')
    receipt: Path = safe(root, RECEIPT)
    if backend == 'neutral' and legacy:
        if not receipt.exists():
            blockers.append(
                'Legacy data beside neutral backend; review'
            )
        else:
            saved: dict[str, Any] = json.loads(receipt.read_text())
            if not isinstance(saved, dict):
                raise ValueError('Invalid migration recovery record')
            if saved.get('legacy') != legacy:
                blockers.append(
                    'Legacy files changed after migration'
                )
    if backend == 'legacy':
        key_neutral: str
        for key, pair in PATHS.items():
            key_neutral = pair[1]
            if key not in GUIDANCE and files(root, key_neutral):
                blockers.append(
                    f'Neutral data beside legacy backend: {key}'
                )
    # Additional provider payloads require explicit reconciliation.
    provider: str
    for provider in ('.opencode', '.codex'):
        for key, pair in PATHS.items():
            alternate: str = pair[0].replace(
                '.claude/', provider + '/', 1
            )
            if files(root, alternate):
                blockers.append(
                    f'Additional provider data: {alternate}'
                )
    return {
        'repo': str(root),
        'backend': backend,
        'selection': 'configured' if selected else 'inferred',
        'paths': resolved,
        'legacy': legacy,
        'neutral': neutral,
        'blockers': sorted(set(blockers)),
    }


def destination(relative: str) -> str:
    '''
    Map a known legacy file to its neutral destination.

    '''
    pair: tuple[str, str]
    for pair in sorted(PATHS.values(), key=lambda p: -len(p[0])):
        if relative == pair[0] or relative.startswith(pair[0] + '/'):
            return pair[1] + relative[len(pair[0]) :]
    if relative.startswith('.claude/git_commit_msg_'):
        return '.ai/state/commit-msg/msgs/' + Path(relative).name
    raise ValueError(f'No destination mapping: {relative}')


def preview(root: Path) -> dict[str, Any]:
    '''
    Build a read-only migration plan with a content digest.

    '''
    state: dict[str, Any] = inspect(root)
    setup(root, write=False)
    blockers: list[str] = [
        item
        for item in state['blockers']
        if item.startswith(
            ('Additional provider', 'Legacy files changed')
        )
    ]
    operations: list[dict[str, str]] = []
    source: str
    target: str
    seen: set[str] = set()
    sources: dict[str, str] = state['legacy']
    if (
        state['backend'] == 'neutral'
        and
        state['selection'] == 'configured'
        and
        (not state['legacy'] or safe(root, RECEIPT).exists())
    ):
        sources = {}
        blockers = list(state['blockers'])
    for source in sources:
        target = destination(source)
        if target in seen:
            blockers.append(f'Multiple sources for {target}')
        seen.add(target)
        source_path: Path = safe(root, source)
        target_path: Path = safe(root, target)
        payload: bytes = source_path.read_bytes()
        # Regenerate pending patches and executable plans; never
        # substitute paths inside their code or diffs.
        if source_path.suffix in ('.patch', '.py', '.sh', '.xsh'):
            blockers.append(
                f'Resolve pending workflow helper: {source}'
            )
        rewritten: bool = source == PATHS['review_context'][0]
        if rewritten:
            pair: tuple[str, str]
            for pair in sorted(
                PATHS.values(), key=lambda p: -len(p[0])
            ):
                payload = payload.replace(
                    pair[0].encode(), pair[1].encode()
                )
        if target_path.exists():
            if (
                not target_path.is_file()
                or target_path.read_bytes() != payload
            ):
                blockers.append(f'Destination conflict: {target}')
        operations.append(
            {
                'source': source,
                'target': target,
                'source_sha256': state['legacy'][source],
                'target_sha256': digest(payload),
                'action': 'rewrite-review-paths'
                if rewritten
                else 'copy',
            }
        )
    result: dict[str, Any] = {
        'repo': str(root),
        'backend': state['backend'],
        'legacy': state['legacy'],
        'operations': operations,
        'blockers': sorted(set(blockers)),
    }
    result['sha256'] = digest(
        json.dumps(result, sort_keys=True).encode()
    )
    return result


def setup(root: Path, write: bool = True) -> None:
    '''
    Preflight configuration paths and install state ignores.

    '''
    ignore: Path = safe(root, '.gitignore')
    current: str = ignore.read_text() if ignore.exists() else ''
    begin: str = '# BEGIN ai.skillz: workflow-state'
    end: str = '# END ai.skillz: workflow-state'
    if begin in current or end in current:
        if current.count(begin) != 1 or current.count(end) != 1:
            raise ValueError('Malformed workflow-state ignore block')
        if IGNORE.rstrip() not in current:
            raise ValueError('Modified workflow-state ignore block')
    # Refuse a broad ignore hiding trackable configuration.
    candidate: str
    for candidate in (MARKER, *[PATHS[k][1] for k in GUIDANCE]):
        check = subprocess.run(
            ['git', 'check-ignore', '-q', '--no-index', candidate],
            cwd=root,
        )
        if check.returncode not in (0, 1):
            raise ValueError('Cannot inspect Git ignore rules')
        if check.returncode == 0:
            raise ValueError(
                f'Configuration is ignored: {candidate}'
            )
    safe(root, MARKER)
    safe(root, RECEIPT)
    if not write:
        return
    if begin not in current:
        ignore.write_text(
            current + ('\n' if current else '') + IGNORE
        )
    safe(root, MARKER).parent.mkdir(parents=True, exist_ok=True)


def select(root: Path, backend: str) -> None:
    '''
    Publish the worktree backend selection atomically.

    '''
    path: Path = safe(root, MARKER)
    temporary: Path = path.with_name(path.name + '.new')
    with temporary.open('x') as stream:
        json.dump({'version': 1, 'backend': backend}, stream)
        stream.write('\n')
    os.replace(temporary, path)


def apply(root: Path, expected: str) -> dict[str, Any]:
    '''
    Copy reviewed state before selecting the neutral backend.

    '''
    plan: dict[str, Any] = preview(root)
    if plan['sha256'] != expected:
        raise ValueError('Preview changed; review a new preview')
    if plan['blockers']:
        raise ValueError('; '.join(plan['blockers']))
    state: dict[str, Any] = inspect(root)
    if (
        state['backend'] == 'neutral'
        and
        state['selection'] == 'configured'
        and
        (not state['legacy'] or safe(root, RECEIPT).exists())
    ):
        if state['blockers']:
            raise ValueError('; '.join(state['blockers']))
        return state
    # Preflight paths and contents before filesystem mutation.
    ignore: Path = safe(root, '.gitignore')
    old_ignore: bytes | None = (
        ignore.read_bytes() if ignore.exists() else None
    )
    created: list[Path] = []
    setup(root)
    try:
        operation: dict[str, str]
        for operation in plan['operations']:
            source: Path = safe(root, operation['source'])
            target: Path = safe(root, operation['target'])
            payload: bytes = source.read_bytes()
            if digest(payload) != operation['source_sha256']:
                raise ValueError('Source changed during migration')
            if operation['action'] == 'rewrite-review-paths':
                pair: tuple[str, str]
                for pair in sorted(
                    PATHS.values(), key=lambda p: -len(p[0])
                ):
                    payload = payload.replace(
                        pair[0].encode(), pair[1].encode()
                    )
            if target.exists():
                if target.read_bytes() != payload:
                    raise ValueError(
                        'Destination changed during migration'
                    )
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                created.append(target)
                os.chmod(target, 0o600)
                stream.write(payload)
            target.chmod(source.stat().st_mode & 0o777)
        if inspect(root)['legacy'] != plan['legacy']:
            raise ValueError('Legacy data changed during migration')
        receipt: Path = safe(root, RECEIPT)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open('x') as stream:
            created.append(receipt)
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        select(root, 'neutral')
    except Exception:
        path: Path
        for path in reversed(created):
            path.unlink()
        if old_ignore is None:
            ignore.unlink(missing_ok=True)
        else:
            ignore.write_bytes(old_ignore)
        raise
    return inspect(root)


def main() -> None:
    '''
    Dispatch inspection, initialization, or explicit migration.

    '''
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        __doc__
    )
    parser.add_argument(
        'command', choices=('status', 'prepare', 'migrate')
    )
    parser.add_argument('repo')
    parser.add_argument('--apply', metavar='PREVIEW_SHA256')
    args: argparse.Namespace = parser.parse_args()
    root: Path = Path(
        subprocess.check_output(
            ['git', '-C', args.repo, 'rev-parse', '--show-toplevel'],
            text=True,
        ).strip()
    ).resolve()
    if args.apply and args.command != 'migrate':
        parser.error('--apply is only valid with migrate')
    result: dict[str, Any]
    if args.command == 'migrate':
        result = (
            apply(root, args.apply) if args.apply else preview(root)
        )
    else:
        result = inspect(root)
        if args.command == 'prepare':
            if result['blockers']:
                raise ValueError('; '.join(result['blockers']))
            setup(root)
            if result['selection'] == 'inferred':
                select(root, result['backend'])
            result = inspect(root)
    print(json.dumps(result, indent=2))
    if result['blockers']:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except (
        ValueError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f'Error: {error}', file=sys.stderr)
        raise SystemExit(1)
