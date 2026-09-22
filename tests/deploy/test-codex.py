#!/usr/bin/env python3
'''
Exercise Codex discovery without credentials or a model turn.

The old hybrid layout passed filesystem checks but Codex silently
skipped its symlinked SKILL.md files. Check that every manifest
skill is discoverable, including commit-plan's commit-msg dependency.

'''
from __future__ import annotations

import json
import os
from pathlib import Path
from queue import Queue
import shutil
import subprocess
import tempfile
from threading import Thread
from typing import Any


def check_loader(
    repo: Path,
    env: dict[str, str],
    expected: set[str],
    source: Path,
) -> None:
    '''
    Ask the app server for its registry and verify canonical sources.

    '''
    with tempfile.TemporaryFile(mode='w+') as log:
        process: subprocess.Popen[str] = subprocess.Popen(
            ['codex', 'app-server'],
            cwd=repo,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
        )
        messages: Queue[str] = Queue()

        def collect() -> None:
            if process.stdout is None:
                raise RuntimeError('app-server stdout unavailable')
            line: str
            for line in process.stdout:
                messages.put(line)

        reader: Thread = Thread(target=collect, daemon=True)
        reader.start()

        def send(message: dict[str, Any]) -> None:
            if process.stdin is None:
                raise RuntimeError('app-server stdin is unavailable')
            process.stdin.write(json.dumps(message) + '\n')
            process.stdin.flush()

        def receive(request_id: int) -> dict[str, Any]:
            message: dict[str, Any]
            while True:
                message = json.loads(messages.get(timeout=30))
                if message.get('id') == request_id:
                    if 'error' in message:
                        raise RuntimeError(message)
                    return message['result']

        try:
            send({
                'id': 1,
                'method': 'initialize',
                'params': {
                    'clientInfo': {
                        'name': 'ai-skillz-discovery-test',
                        'version': '1',
                    },
                },
            })
            receive(1)
            send({'method': 'initialized'})
            send({
                'id': 2,
                'method': 'skills/list',
                'params': {
                    'cwds': [str(repo)],
                    'forceReload': True,
                },
            })
            listing: dict[str, Any] = receive(2)['data'][0]
            if listing['errors']:
                raise RuntimeError(listing['errors'])
            found: set[str] = set()
            skill: dict[str, Any]
            for skill in listing['skills']:
                if skill['scope'] != 'repo':
                    continue
                name: str = skill['name']
                found.add(name)
                if not skill['enabled']:
                    raise RuntimeError(f'Disabled skill: {name}')
                canonical: Path = (
                    source / 'skills' / name / 'SKILL.md'
                )
                if Path(skill['path']).resolve() != canonical:
                    raise RuntimeError(f'Noncanonical skill: {name}')
            if found != expected:
                missing: set[str] = expected - found
                extra: set[str] = found - expected
                raise RuntimeError(
                    f'Skill mismatch: missing={missing}, '
                    f'extra={extra}'
                )
            count: int = len(found)
            print(
                f'PASS: Codex discovers {count} shared skills'
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            reader.join(timeout=1)
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()


def main() -> None:
    '''
    Preserve the user's configuration by deploying in isolation.

    '''
    if shutil.which('codex') is None:
        raise SystemExit(
            'Codex CLI is required for this optional test'
        )
    source: Path = Path(__file__).resolve().parents[2]
    expected: set[str] = set()
    record: str
    records: list[str] = (
        (source / 'deploy-manifest.conf').read_text().splitlines()
    )
    for record in records:
        if record.startswith('skill|'):
            expected.add(record.split('|')[1])
    with tempfile.TemporaryDirectory(
        prefix='ai-skillz-codex-',
    ) as temp:
        fixture: Path = Path(temp)
        repo: Path = fixture / 'repo'
        repo.mkdir()
        env: dict[str, str] = dict(os.environ)
        key: str
        for key in list(env):
            if key.startswith(('CODEX_', 'OPENAI_', 'ANTHROPIC_')):
                env.pop(key)
        for key in (
            'HOME',
            'CODEX_HOME',
            'XDG_CONFIG_HOME',
            'XDG_CACHE_HOME',
            'XDG_DATA_HOME',
        ):
            location: Path = fixture / key.lower()
            location.mkdir()
            env[key] = str(location)
        subprocess.run(
            ['git', 'init', '-q', str(repo)],
            env=env,
            check=True,
            timeout=30,
        )
        subprocess.run(
            [
                'bash', str(source / 'scripts/deploy.sh'),
                'all', str(repo), '--harness', 'codex',
            ],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=120,
        )
        check_loader(repo, env, expected, source)


if __name__ == '__main__':
    main()
