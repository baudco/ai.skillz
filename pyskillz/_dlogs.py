# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
List saved dialogs without starting a harness or model turn.

'''

import argparse
import json
import os
from collections import Counter
from pathlib import Path
import sqlite3
import subprocess
import sys

from ._stores import (
    codex_sessions,
    opencode_sessions,
    claude_sessions,
)


def list_dialogs(
    path: str|Path|None = '.',
    harness: str|list[str]|None = None,
    all: bool = False,
    all_sources: bool = False,
) -> list[dict]:
    '''
    Return metadata; all=True overrides harness and cwd scope.

    A None harness selects every supported harness at the given path.
    Missing stores are skipped in multi-harness discovery. Invalid
    existing stores raise an error rather than silently losing data.

    '''
    names: list[str] = (
        ['codex', 'opencode', 'claude']
        if (
            all
            or
            harness is None
        )
        else [harness]
        if isinstance(harness, str)
        else harness
    )
    aliases: dict[str, str] = {
        'cx': 'codex',
        'cld': 'claude',
        'oc': 'opencode',
    }
    name: str
    names = list(
        dict.fromkeys(
            aliases.get(name, name) for name in names
        )
    )
    unknown: set[str] = set(names) - {'codex', 'opencode', 'claude'}
    if unknown:
        raise ValueError('Unknown harness: ' + ', '.join(unknown))
    cwd: str|None = None
    if (
        not all
        and
        path is not None
    ):
        cwd = str(Path(path).expanduser().resolve())
    data: Path = Path(
        os.environ.get(
            'XDG_DATA_HOME',
            str(Path.home() / '.local/share'),
        )
    ).expanduser()
    homes: dict[str, Path] = {
        'codex': Path(
            os.environ.get(
                'CODEX_HOME',
                str(Path.home() / '.codex'),
            )
        ),
        'opencode': Path(
            os.environ.get(
                'OPENCODE_DATA_DIR',
                str(data / 'opencode'),
            )
        ),
        'claude': Path(
            os.environ.get(
                'CLAUDE_CONFIG_DIR',
                str(Path.home() / '.claude'),
            )
        ),
    }
    readers: dict = {
        'codex': codex_sessions,
        'opencode': opencode_sessions,
        'claude': claude_sessions,
    }
    records: list[dict] = []
    name: str
    for name in names:
        home: Path = homes[name].expanduser().resolve()
        if (
            name == 'codex'
            and
            not (home / 'state_5.sqlite').is_file()
            and
            len(names) > 1
        ):
            continue
        records.extend(readers[name](home, cwd, all_sources or all))
    unique: dict[tuple[str, str], dict] = {}
    record: dict
    for record in sorted(records, key=lambda r: r['updated_at']):
        unique[record['harness'], record['id']] = record
    return sorted(
        unique.values(),
        key=lambda r: (-r['updated_at'], r['harness'], r['id']),
    )


def name2id(
    path: str|Path|None = '.',
    harness: str|list[str]|None = None,
    all: bool = False,
    all_sources: bool = False,
) -> dict[str, str]:
    '''
    Return name-to-dialog-ID mappings without dropping duplicate
    names.

    Duplicate names gain a [harness:id] suffix. list_dialogs retains
    exact raw names and harness metadata for callers building
    launchers.

    '''
    records: list[dict] = list_dialogs(
        path,
        harness,
        all=all,
        all_sources=all_sources,
    )
    row: dict
    counts: Counter = Counter(row['name'] for row in records)
    reserved: set[str] = set(counts)
    result: dict[str, str] = {}
    row: dict
    for row in records:
        name: str = row['name']
        if counts[name] > 1:
            backend: str = row['harness']
            did: str = row['id']
            name = f'{name} [{backend}:{did}]'
            while (
                name in reserved
                or
                name in result
            ):
                name += '#'
        result[name] = row['id']
    return result


def _worktree_name(cwd: str) -> str:
    '''
    Identify a linked worktree at the recorded cwd, if accessible.

    Git's common directory distinguishes linked worktrees from main
    checkouts and submodules. This does not locate a running agent.

    '''
    if not Path(cwd).is_absolute():
        return ''
    key: str
    value: str
    env: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith('GIT_')
    }
    try:
        result: subprocess.CompletedProcess = subprocess.run(
            [
                'git', 'rev-parse', '--path-format=absolute',
                '--show-toplevel', '--git-dir', '--git-common-dir',
            ],
            cwd=cwd, env=env, capture_output=True, text=True,
            timeout=2, check=True,
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return ''
    paths: list[str] = result.stdout.splitlines()
    if len(paths) != 3:
        return ''
    if paths[1] == paths[2]:
        return ''
    return Path(paths[0]).name


def table(sessions: list[dict], show_cwd: bool = True) -> str:
    '''
    Render full IDs and cap displayed names at 36 characters.

    '''
    keys: list[str] = ['name', 'id']
    header: list[str] = ['NAME', 'DIALOG ID']
    if show_cwd:
        keys.append('cwd')
        header.append('CWD')
    keys.append('wkt')
    header.append('WKT')
    keys.append('harness')
    header.append('HARNESS')
    rows: list[list[str]] = [header]
    home: str = str(Path.home())
    home_prefix: str = home.rstrip(os.sep) + os.sep
    worktrees: dict[str, str] = {}
    session: dict
    for session in sessions:
        display: dict = dict(session)
        cwd: str = str(display.get('cwd', ''))
        if cwd not in worktrees:
            worktrees[cwd] = _worktree_name(cwd)
        display['wkt'] = worktrees[cwd]
        if cwd == home:
            display['cwd'] = '~'
        elif cwd.startswith(home_prefix):
            display['cwd'] = '~' + os.sep + cwd[len(home_prefix):]
        char: str
        key: str
        rows.append(
            [
                ' '.join(
                    ''.join(
                        char if char.isprintable() else ' '
                        for char in str(display.get(key, ''))
                    ).split()
                )
                for key in keys
            ]
        )
        if len(rows[-1][0]) > 36:
            rows[-1][0] = rows[-1][0][:35] + '…'
    row: list[str]
    index: int
    widths: list[int] = [
        max(len(row[index]) for row in rows)
        for index in range(len(keys))
    ]
    row: list[str]
    index: int
    value: str
    return '\n'.join(
        '  '.join(
            value.ljust(widths[index])
            for index, value in enumerate(row)
        ).rstrip()
        for row in rows
    )


def main(argv: list[str]|None = None) -> int:
    '''
    Print a table by default, with JSON for launcher integration.

    '''
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog='ai.dlogs',
        description=__doc__,
        add_help=False,
    )
    parser.add_argument('--help', action='help')
    parser.add_argument(
        'repo',
        nargs='?',
        default='.',
        help='exact session cwd (default: current directory)',
    )
    parser.add_argument(
        '-h', '--harness',
        choices=[
            'codex', 'cx', 'opencode', 'oc', 'claude', 'cld', 'all',
        ],
        default='all',
        help='harness to list (default: all, scoped to cwd)',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='every harness, cwd and source',
    )
    parser.add_argument('-a', '--all-repos', action='store_true')
    parser.add_argument('--all-sources', action='store_true')
    parser.add_argument('--json', action='store_true')
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        sessions: list[dict] = list_dialogs(
            None if args.all_repos else args.repo,
            None if args.harness == 'all' else args.harness,
            all=args.all,
            all_sources=args.all_sources,
        )
    except (
        OSError,
        ValueError,
        sqlite3.Error,
    ) as error:
        parser.exit(1, f'ai.dlogs: {error}\n')
    output: str = (
        json.dumps(sessions, indent=2)
        if args.json
        else table(sessions)
    )
    if (
        not args.json
        and
        sys.stdout.isatty()
        and
        not os.environ.get('NO_COLOR')
        and
        os.environ.get('TERM') != 'dumb'
    ):
        header: str
        separator: str
        body: str
        (
            header,
            separator,
            body,
        ) = output.partition('\n')
        output = f'\x1b[90m{header}\x1b[0m{separator}{body}'
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
