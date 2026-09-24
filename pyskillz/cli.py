# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Shell commands and terminal formatting for ai.dlogs.

The installed command, python -m pyskillz, source script and Xontrib
all call main(). Dialog operations live in pyskillz.dialogs; this
module parses arguments and formats their results for people or JSON.

'''

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

# Direct source execution supports skill deployments without pip.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'pyskillz'

from . import dialogs
from .wkt import WktLookup


def format_dialog_table(
    sessions: list[dict],
    show_cwd: bool = True,
) -> str:
    '''
    Format dialog metadata and worktree labels for terminal display.

    `main()` passes newest-first `dialogs.list_dialogs()` records
    here; caller order and input dictionaries remain unchanged.
    Display `updated_at` Unix seconds as UTC minutes, leaving
    invalid/missing times blank. Reuse one `WktLookup` instance
    for the WKT column, which can reflect confirmed `/open-wkt` or
    index relations even when saved cwd names the main checkout.
    `show_cwd=False` hides only the CWD column.

    Keep full IDs, cap names at 36 characters with an ellipsis,
    abbreviate home paths and neutralize control characters. Return
    plain text; `main()` adds optional header color. JSON/Python
    metadata bypasses this formatting and contains neither shortened
    names nor WKT labels.

    '''
    keys: list[str] = ['name', 'id', 'updated']
    header: list[str] = ['NAME', 'DIALOG ID', 'UPDATED (UTC)']
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
    worktrees: WktLookup = WktLookup()
    session: dict
    for session in sessions:
        display: dict = dict(session)
        cwd: str = str(display.get('cwd', ''))
        roots: set[str] = worktrees.roots(
            cwd, display.get('harness', ''), display.get('id', ''),
        )
        display['wkt'] = (
            '(multiple)' if len(roots) > 1
            else Path(next(iter(roots))).name if roots else ''
        )
        updated: object = display.get('updated_at')
        display['updated'] = ''
        if isinstance(updated, (int, float)):
            try:
                display['updated'] = datetime.fromtimestamp(
                    updated, timezone.utc,
                ).strftime('%Y-%m-%d %H:%M')
            except (
                OverflowError,
                OSError,
                ValueError,
            ):
                pass
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
    Serve package, source-script and Xontrib dialog commands.

    Normal invocations call `dialogs.list_dialogs()` with the CLI
    filters and print either `format_dialog_table()` output or
    unmodified JSON records. Color is applied only to eligible
    terminal headers. The first token `index` delegates to
    `index_main()` for metadata preview/apply or explicit recording;
    spell a directory literally named index as `./index`.

    The alias and `pyskillz/cli.py` share this dispatcher, so
    `/open-wkt` can record through the canonical source without a
    package install. Return zero on success; argument/store failures
    exit nonzero.

    '''
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['index']:
        return index_main(argv[1:])
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog='ai.dlogs',
        description='List local dialogs and their worktrees.',
        epilog='See ai.dlogs index --help for WKT relations.',
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
        sessions: list[dict] = dialogs.list_dialogs(
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
        else format_dialog_table(sessions)
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


def index_main(argv: list[str]) -> int:
    '''
    Dispatch the metadata-index CLI modes and report their outcomes.

    Called by `cli.main()` after consuming the `index` subcommand.
    Default mode builds and saves a preview, printing WKT matches,
    counts, warnings and a concrete Xonsh apply command. Empty
    proposals omit that command; `--json` exposes the proposal and
    its pin to tooling.

    `--apply` requires a digest and permits explicit ambiguous
    choices. `--record` requires a worktree and delegates current-ID
    verification to the invoking skill or human. Invalid mode
    combinations are CLI errors. Operational failures exit nonzero
    with context; successful apply/record calls print the number of
    WKT relations written.

    '''
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog='ai.dlogs index',
        description='Find WKT relations for existing dialogs.',
    )
    parser.add_argument('repo', nargs='?', default='.')
    modes: argparse._MutuallyExclusiveGroup = (
        parser.add_mutually_exclusive_group()
    )
    modes.add_argument(
        '--apply', type=Path, help='apply a reviewed preview file',
    )
    modes.add_argument(
        '--record', nargs=2, metavar=('HARNESS', 'ID'),
        help='record an explicitly known WKT relation',
    )
    parser.add_argument('--sha256')
    parser.add_argument('--choose', action='append', default=[])
    parser.add_argument('--worktree')
    parser.add_argument('--no-logs', action='store_true')
    parser.add_argument('--json', action='store_true')
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        if args.apply:
            if not args.sha256:
                parser.error('--apply requires --sha256')
            if args.worktree:
                parser.error('--worktree requires --record')
            changed: int = dialogs.apply_wkt_preview(
                args.repo, args.apply, args.sha256, args.choose,
            )
            print('WKT relations written:', changed)
        elif args.record:
            if (
                not args.worktree
                or
                args.sha256
                or
                args.choose
            ):
                parser.error('--record requires only --worktree')
            changed = dialogs.record_wkt_relation(
                args.repo, *args.record, args.worktree,
            )
            print('WKT relations written:', changed)
        else:
            if (
                args.sha256
                or
                args.choose
                or
                args.worktree
            ):
                parser.error('Apply/record options need their mode')
            data: dict = dialogs.preview_wkt_relations(
                args.repo, logs=not args.no_logs,
            )
            path: Path
            digest: str
            path, digest = dialogs.save_wkt_preview(data)
            if args.json:
                print(json.dumps({
                    'path': str(path), 'sha256': digest,
                    'data': data,
                }, indent=2))
            else:
                if data['entries']:
                    print('STATUS     HARNESS:DIALOG ID / NAME')
                else:
                    print('No new WKT relations to apply.')
                entry: dict
                for entry in data['entries']:
                    status: str = entry['status'].upper()
                    harness: str = entry['harness']
                    did: str = entry['id']
                    label: str = json.dumps(
                        harness + ':' + did + ' ' + entry['name'],
                    )
                    print(f'{status:<10} {label}')
                    candidate: dict
                    for candidate in entry['candidates']:
                        target: str = json.dumps(
                            candidate['worktree'],
                        )
                        evidence: str = ', '.join(
                            candidate['evidence'],
                        )
                        print(f'  {target} [{evidence}]')
                print('Unresolved:', len(data['unresolved']))
                print('Already recorded:', data['confirmed'])
                warning: str
                for warning in data['warnings']:
                    print('Warning:', json.dumps(warning))
                print('Preview:', json.dumps(str(path)))
                print('SHA-256:', digest)
                repo: str = str(Path(args.repo).resolve())
                preview_path: str = str(path)
                if data['entries']:
                    print(
                        f'Apply: ai.dlogs index @({repo!r}) '
                        f'--apply @({preview_path!r}) '
                        f'--sha256 {digest}'
                    )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        parser.exit(1, 'ai.dlogs index: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
