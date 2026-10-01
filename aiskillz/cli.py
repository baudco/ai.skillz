# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Shell commands and terminal formatting for ai.dlogs.

The installed command, python -m aiskillz, source script and Xontrib
all call main(). Dialog operations live in aiskillz.dialogs; this
module parses arguments and formats their results for people or JSON.

'''

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys

# Direct source execution supports skill deployments without pip.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'aiskillz'

from . import dialogs
from ._resume import resume_target
from .wkt import WktLookup


def _display_text(value: object) -> str:
    '''
    Remove terminal controls and repeated whitespace from a cell.

    `format_dialog_table()` uses this for both rows and context
    lines. Python and JSON callers retain the original values.

    '''
    char: str
    return ' '.join(
        ''.join(
            char if char.isprintable() else ' '
            for char in str(value)
        ).split()
    )


def _terminal_color_enabled() -> bool:
    '''Use color only for an interactive terminal that permits it.'''
    return (
        sys.stdout.isatty()
        and not os.environ.get('NO_COLOR')
        and os.environ.get('TERM') != 'dumb'
    )


def _grey_label(label: str, color: bool) -> str:
    '''Dim a preview label without coloring its value.'''
    return f'\x1b[90m{label}\x1b[0m' if color else label


def _highlight(value: str, code: int, color: bool) -> str:
    '''Color one preview value while preserving plain output.'''
    return f'\x1b[{code}m{value}\x1b[0m' if color else value


def _shell_commands(
    action: str,
    argv: list[str],
    xonsh_command: str,
) -> list[tuple[str, str]]:
    '''Format a preview action for Xonsh and POSIX shell users.

    `index_main()` uses this for both Resume and Apply. Ordinary
    `shlex.join()` output works in both shells. POSIX's apostrophe
    quoting does not parse in Xonsh, so that case gets two commands.

    '''
    posix_command: str = shlex.join(argv)
    if any("'" in arg for arg in argv):
        return [
            (f'{action} (xonsh):', xonsh_command),
            (f'{action} (POSIX sh):', posix_command),
        ]
    return [(f'{action} (xonsh/POSIX sh):', posix_command)]


def format_dialog_table(
    sessions: list[dict],
    show_cwd: bool = True,
    show_timestamps: bool = False,
    show_did: bool = False,
) -> str:
    '''
    Format dialog metadata and worktree labels for terminal display.

    `main()` passes newest-first `dialogs.list_dialogs()` records
    here; caller order and input dictionaries remain unchanged.
    Show `updated_at` as UTC minutes only when requested, leaving
    invalid/missing times blank. Reuse one `WktLookup` instance
    for the WKT column, which can reflect confirmed `/open-wkt` or
    index relations even when saved cwd names the main checkout.
    The sort rule appears above the table. Uniform CWD and harness
    values follow it; `show_cwd=False` hides CWD in both places.

    Show full IDs only when requested. Cap names at 36 characters
    with an ellipsis, abbreviate home paths and neutralize control
    characters. Return plain text; `main()` adds optional header
    color. JSON/Python metadata bypasses this formatting and
    contains neither shortened names nor WKT labels.

    '''
    displays: list[dict[str, str]] = []
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
        if show_timestamps:
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
        values: dict[str, str] = {
            key: _display_text(value)
            for key, value in display.items()
        }
        if len(values.get('name', '')) > 36:
            values['name'] = values['name'][:35] + '…'
        displays.append(values)

    context: list[str] = [
        'sort-by: "last-update-time" (newest first)',
    ]
    cwd_values: set[str] = {
        row.get('cwd', '') for row in displays
    }
    harness_values: set[str] = {
        row.get('harness', '') for row in displays
    }
    uniform_cwd: bool = (
        show_cwd
        and
        len(cwd_values) == 1
        and
        bool(next(iter(cwd_values)))
    )
    uniform_harness: bool = (
        len(harness_values) == 1
        and
        bool(next(iter(harness_values)))
    )
    if uniform_cwd:
        context.append('CWD=' + next(iter(cwd_values)))
    if uniform_harness:
        context.append('HARNESS=' + next(iter(harness_values)))

    columns: list[tuple[str, str]] = [
        ('name', 'NAME'),
    ]
    if show_did:
        columns.append(('id', 'DIALOG ID'))
    columns.append(('wkt', 'WKT'))
    if show_timestamps:
        columns.append(('updated', 'UPDATED (UTC)'))
    if (
        show_cwd
        and
        not uniform_cwd
    ):
        columns.append(('cwd', 'CWD'))
    if not uniform_harness:
        columns.append(('harness', 'HARNESS'))
    keys: list[str] = [key for key, _ in columns]
    rows: list[list[str]] = [
        [label for _, label in columns]
    ]
    row: dict[str, str]
    for row in displays:
        rows.append([row.get(key, '') for key in keys])
    row: list[str]
    index: int
    widths: list[int] = [
        max(len(row[index]) for row in rows)
        for index in range(len(keys))
    ]
    row: list[str]
    index: int
    value: str
    table: str = '\n'.join(
        '  '.join(
            value.ljust(widths[index])
            for index, value in enumerate(row)
        ).rstrip()
        for row in rows
    )
    if context:
        return '\n'.join(context) + '\n\n' + table
    return table


def main(argv: list[str]|None = None) -> int:
    '''
    Serve package, source-script and Xontrib dialog commands.

    Normal invocations call `dialogs.list_dialogs()` with the CLI
    filters and print either `format_dialog_table()` output or
    unmodified JSON records. Color is applied only to eligible
    terminal headers. The first token `index` delegates to
    `index_main()` for metadata preview/apply or explicit recording;
    spell a directory literally named index as `./index`.

    The alias and `aiskillz/cli.py` share this dispatcher, so
    `/open-wkt` can record through the canonical source without a
    package install. Return zero on success; argument/store failures
    exit nonzero.

    '''
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['index']:
        return index_main(argv[1:])
    if argv[:1] == ['resume']:
        return resume_main(argv[1:])
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog='ai.dlogs',
        description='List local dialogs and their worktrees.',
        epilog='See ai.dlogs index --help for WKT relations.',
    )
    parser.add_argument(
        'repo',
        nargs='?',
        default='.',
        help='exact session cwd (default: current directory)',
    )
    parser.add_argument(
        '-b', '--harness',
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
    parser.add_argument(
        '-t', '--timestamps', action='store_true',
        help='show last-update time (UTC); newest first regardless',
    )
    parser.add_argument(
        '--did', action='store_true',
        help='show dialog IDs in the terminal table',
    )
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
        else format_dialog_table(
            sessions,
            show_timestamps=args.timestamps,
            show_did=args.did,
        )
    )
    if not args.json and _terminal_color_enabled():
        context: str
        context_separator: str
        table: str
        context, context_separator, table = output.partition(
            '\n\n',
        )
        if not context_separator:
            table = context
            context = ''
        header: str
        separator: str
        body: str
        header, separator, body = table.partition('\n')
        table = f'\x1b[90m{header}\x1b[0m{separator}{body}'
        if context_separator:
            colored: list[str] = []
            line: str
            for line in context.splitlines():
                label: str
                separator: str
                value: str
                delimiter: str = (
                    ': ' if line.startswith('sort-by: ') else '='
                )
                label, separator, value = line.partition(delimiter)
                colored.append(
                    f'\x1b[90m{label}{separator}\x1b[0m{value}'
                )
            context = '\n'.join(colored)
        output = (
            context + context_separator + table
            if context_separator else table
        )
    print(output)
    return 0


def resume_main(argv: list[str]|None = None) -> int:
    '''
    Resolve a name or ID, then run the selected dialog's harness.

    `ai.resume`, the Xontrib alias and the source alias all reach
    this entrypoint. `resume_target()` performs selection and WKT
    lookup without spawning. Dry-run prints the exact argv and cwd;
    normal mode inherits the terminal and returns the harness status.

    '''
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog='ai.resume',
        description='Resume a dialog by name or ID in its harness.',
    )
    parser.add_argument('name', metavar='NAME_OR_ID')
    parser.add_argument(
        '--repo', default='.',
        help='saved cwd to search (default: current directory)',
    )
    parser.add_argument(
        '-b', '--harness',
        choices=[
            'codex', 'cx', 'opencode', 'oc', 'claude', 'cld',
        ],
        help='narrow duplicate names or IDs to one harness',
    )
    parser.add_argument('-a', '--all-repos', action='store_true')
    parser.add_argument('--id', help='narrow duplicate names by ID')
    parser.add_argument(
        '--cwd', help='override the harness launch directory',
    )
    parser.add_argument('--dry-run', action='store_true')
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        target: dict = resume_target(
            args.name,
            repo=args.repo,
            harness=args.harness,
            all_repos=args.all_repos,
            dialog_id=args.id,
            cwd=args.cwd,
        )
        if args.dry_run:
            print(json.dumps(target, indent=2))
            return 0
        command: list[str] = target['argv']
        if shutil.which(command[0]) is None:
            raise ValueError(
                'Harness command is unavailable: ' + command[0]
            )
        result: subprocess.CompletedProcess = subprocess.run(
            command,
            cwd=target['cwd'],
            check=False,
        )
        return result.returncode
    except (
        OSError,
        ValueError,
        sqlite3.Error,
    ) as error:
        parser.exit(1, 'ai.resume: ' + str(error) + '\n')


def index_main(argv: list[str]) -> int:
    '''
    Dispatch the metadata-index CLI modes and report their outcomes.

    Called by `cli.main()` after consuming the `index` subcommand.
    Default mode builds and saves a preview, printing separated WKT
    matches, exact-ID resume commands, counts, warnings and a
    reviewed apply command. Commands shared by Xonsh and POSIX sh
    appear once; paths or names needing different quoting get both
    forms. The common legacy-owner evidence marker stays in the
    saved preview but is omitted from repeated terminal rows.
    Empty proposals omit the apply command; `--json` exposes the
    complete proposal and its pin to tooling.

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
                color: bool = _terminal_color_enabled()
                if data['entries']:
                    print(_grey_label(
                        'STATUS     HARNESS:DIALOG ID / NAME',
                        color,
                    ))
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
                    print(
                        _grey_label(f'{status:<10}', color),
                        _highlight(label, 36, color),
                    )
                    if entry['name'] != '(metadata)':
                        resume_label: str
                        resume_command: str
                        for resume_label, resume_command in _shell_commands(
                            'Resume',
                            [
                                'ai.resume', entry['name'],
                                '-a', '-b', harness, '--id', did,
                            ],
                            f'ai.resume @({entry["name"]!r}) '
                            f'-a -b {harness} --id @({did!r})',
                        ):
                            print(
                                _grey_label(resume_label, color),
                                resume_command,
                            )
                    candidate: dict
                    for candidate in entry['candidates']:
                        target: str = json.dumps(
                            candidate['worktree'],
                        )
                        evidence: str = ', '.join(
                            item for item in candidate['evidence']
                            if item != 'legacy-owner-matching-dialog-id'
                        )
                        detail: str = f' [{evidence}]' if evidence else ''
                        print(
                            '  ' + _highlight(target, 34, color)
                            + detail,
                        )
                    print()
                print(
                    _grey_label('Unresolved:', color),
                    len(data['unresolved']),
                )
                print(
                    _grey_label('Already recorded:', color),
                    data['confirmed'],
                )
                warning: str
                for warning in data['warnings']:
                    print(
                        _grey_label('Warning:', color),
                        json.dumps(warning),
                    )
                print(
                    _grey_label('Preview:', color),
                    json.dumps(str(path)),
                )
                print(_grey_label('SHA-256:', color), digest)
                repo: str = str(Path(args.repo).resolve())
                preview_path: str = str(path)
                if data['entries']:
                    apply_label: str
                    apply_command: str
                    for apply_label, apply_command in _shell_commands(
                        'Apply',
                        [
                            'ai.dlogs', 'index', repo,
                            '--apply', preview_path,
                            '--sha256', digest,
                        ],
                        f'ai.dlogs index @({repo!r}) '
                        f'--apply @({preview_path!r}) '
                        f'--sha256 {digest}',
                    ):
                        print(
                            _grey_label(apply_label, color),
                            apply_command,
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
