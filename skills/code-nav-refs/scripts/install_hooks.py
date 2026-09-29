'''
Preview or explicitly install a blocking final-answer citation hook.

'''
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

from code_refs import git_root


def proposed_config(
    current: dict,
    command: str,
) -> dict:
    '''
    Append one Stop handler without overwriting existing hooks.

    '''
    data = json.loads(json.dumps(current))
    hooks = data.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('hooks must be an object')
    stop = hooks.setdefault('Stop', [])
    if not isinstance(stop, list):
        raise ValueError('hooks.Stop must be a list')
    for group in stop:
        if not isinstance(group, dict):
            raise ValueError('Stop groups must be objects')
        handlers = group.get('hooks')
        if not isinstance(handlers, list):
            raise ValueError('Stop group hooks must be a list')
        if any(
            isinstance(handler, dict)
            and handler.get('command') == command
            for handler in handlers
        ):
            return data
    stop.append({
        'hooks': [{
            'type': 'command',
            'command': command,
            'timeout': 10,
        }],
    })
    return data


def hook_source(root: Path, harness: str) -> Path:
    '''
    Locate the deployed skill in this exact consumer worktree.

    '''
    paths = (
        root / '.ai/ai.skillz/skills/code-nav-refs/scripts',
        root / (
            '.claude/skills/code-nav-refs/scripts'
            if harness == 'claude'
            else '.agents/skills/code-nav-refs/scripts'
        ),
    )
    for folder in paths:
        hook = folder / 'stop_hook.py'
        if hook.is_file():
            return hook
    raise ValueError(
        'Deploy code-nav-refs into this worktree before '
        'installing its Stop hook'
    )


def install(
    root: Path,
    harness: str,
    *,
    apply: bool = False,
) -> Path:
    '''
    Review a project hook configuration before optionally writing.

    '''
    root = root.resolve(strict=True)
    if git_root(root) != root:
        raise ValueError('repo must be its exact Git worktree root')
    if harness == 'opencode':
        target = root / '.opencode/plugins/code-nav-refs.js'
        if (
            target.parent.is_symlink()
            or target.parent.parent.is_symlink()
        ):
            raise ValueError(
                'OpenCode plugin directory is a symlink'
            )
        source = root / (
            '.ai/ai.skillz/providers/opencode/plugins/'
            'code-nav-refs.js'
        )
        if not source.is_file():
            local = Path(__file__).resolve().parents[3]
            if root == local:
                source = local / (
                    'providers/opencode/plugins/code-nav-refs.js'
                )
        if not source.is_file():
            raise ValueError('OpenCode plugin source is unavailable')
        if target.exists() or target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError(
                    'existing OpenCode plugin differs; '
                    'refusing to overwrite it'
                )
            changed = False
        else:
            changed = True
        print(json.dumps({
            'target': str(target),
            'changed': changed,
            'capability': 'instruction only; no final-answer veto',
        }, indent=2))
        if apply and changed:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.path.relpath(
                source, target.parent,
            ))
        return target
    if harness not in ('claude', 'codex'):
        raise ValueError('unknown harness')
    source = hook_source(root, harness)
    config = root / (
        '.claude/settings.json'
        if harness == 'claude'
        else '.codex/hooks.json'
    )
    if config.is_symlink() or config.parent.is_symlink():
        raise ValueError('hook config or directory is a symlink')
    current = (
        json.loads(config.read_text())
        if config.exists() else {}
    )
    if not isinstance(current, dict):
        raise ValueError('existing hook config must be an object')
    command = f'python3 -B {shlex.quote(str(source))}'
    proposed = proposed_config(current, command)
    print(json.dumps({
        'target': str(config),
        'changed': proposed != current,
        'config': proposed,
    }, indent=2))
    if apply and proposed != current:
        config.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            prefix='.code-nav-refs-', dir=config.parent,
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as target:
                json.dump(proposed, target, indent=2)
                target.write('\n')
            os.replace(name, config)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return config


def main(argv: list[str]|None = None) -> int:
    '''
    Provide a preview by default; --apply opts into editing config.

    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=Path)
    parser.add_argument(
        '--harness',
        choices=('claude', 'codex', 'opencode'),
        required=True,
    )
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        install(args.repo, args.harness, apply=args.apply)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
