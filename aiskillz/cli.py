# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Parse shell commands and format ai.dlogs/ai.resume terminal output.

- Installed entry points, python -m aiskillz, source aliases and the
  Xontrib share main()/resume_main().
- aiskillz.dialogs owns metadata discovery and WKT operations.
- This module owns argument parsing and human/JSON presentation.

'''

from datetime import (
    datetime,
    timezone,
)
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys

# /open-wkt can run this file from the canonical source checkout even
# when aiskillz is not installed in its interpreter. Put this tree
# first for the relative imports below; a source invocation must not
# silently use a different editable installation from site-packages.
if __package__ in (
    None,
    '',
):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'aiskillz'

from . import dialogs
from ._resume import (
    resume_target,
    codex_supports_no_daemon,
)
from ._display import (
    DIALOG_NAME_WIDTH,
    DIALOG_NAME_ELLIPSIS,
)
from .wkt import WktLookup
from .wkt._relations import canonical_harness


# ANSI SGR colors used only for interactive display; reset is SGR 0.
_ANSI_GREY: int = 90
_ANSI_BLUE: int = 34
_ANSI_CYAN: int = 36
_INDEX_STATUS_WIDTH: int = 10


def _display_text(value: object) -> str:
    '''
    Normalize one terminal cell without altering stored metadata.

    - `format_dialog_table()` uses this for rows and context fields.
    - Replace terminal controls with spaces and collapse whitespace.
    - Python/JSON callers keep the original values.

    '''
    printable: list[str] = []
    char: str
    for char in str(value):
        if char.isprintable():
            printable.append(char)
        else:
            printable.append(' ')

    return ' '.join(''.join(printable).split())


def _terminal_color_enabled() -> bool:
    '''
    Use color only for an interactive terminal that permits it.

    '''
    return (
        sys.stdout.isatty()
        and not os.environ.get('NO_COLOR')
        and os.environ.get('TERM') != 'dumb'
    )


def _grey_label(label: str, color: bool) -> str:
    '''
    Dim a preview label without coloring its value.

    '''
    if color:
        return f'\x1b[{_ANSI_GREY}m{label}\x1b[0m'

    return label


def _highlight(value: str, code: int, color: bool) -> str:
    '''
    Color one preview value while preserving plain output.

    '''
    if color:
        return f'\x1b[{code}m{value}\x1b[0m'

    return value


def _shell_commands(
    action: str,
    argv: list[str],
    xonsh_command: str,
) -> list[tuple[str, str]]:
    '''
    Render Resume/Apply actions for the user's shell.

    - `index_main()` supplies argv and an explicit Xonsh expression.
    - Use one shared command when shlex.join() parses in both shells.
    - For apostrophes, return separate Xonsh/POSIX forms: POSIX quote
      concatenation is not equivalent to Xonsh's parser syntax.

    '''
    posix_command: str = shlex.join(argv)
    arg: str
    if any("'" in arg for arg in argv):
        return [
            (
                f'{action} (xonsh):',
                xonsh_command,
            ),
            (
                f'{action} (POSIX sh):',
                posix_command,
            ),
        ]
    return [(
        f'{action} (xonsh/POSIX sh):',
        posix_command,
    )]


def format_dialog_table(
    sessions: list[dict],
    show_cwd: bool = True,
    show_timestamps: bool = False,
    show_did: bool = False,
) -> str:
    '''
    Render dialog metadata and WKT labels for terminal users.

    Inputs:
    - `main()` supplies newest-first list_dialogs() results; preserve
      that order and leave all input records unchanged.
    - One WktLookup instance resolves recorded WKTs across the rows,
      including a dialog saved in main cwd but using a linked WKT.

    Presentation:
    - Show the sort rule above the table. Move uniform CWD/HARNESS
      values above the headers instead of repeating a whole column.
    - `show_cwd=False` hides CWD everywhere; IDs/timestamps are
      opt-in.
    - Format valid timestamps as UTC minutes; leave bad/missing ones
      blank.
    - Shorten names using DIALOG_NAME_WIDTH, abbreviate home paths
      and neutralize terminal controls. Keep unavailable relation
      labels.
    - Return plain text; `main()` colors eligible terminal headers.
      JSON/Python metadata retains exact values and has no WKT
      labels.

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
        display['wkt'] = ''
        if len(roots) > 1:
            display['wkt'] = '(multiple)'
        elif roots:
            display['wkt'] = Path(next(iter(roots))).name

        if not roots:
            recorded: set[str] = worktrees.recorded_roots(
                cwd,
                display.get('harness', ''),
                display.get('id', ''),
            )
            root: str
            display['wkt'] = ', '.join(
                Path(root).name + ' (unavailable)'
                for root in sorted(recorded)
            )
        if show_timestamps:
            updated: object = display.get('updated_at')
            display['updated'] = ''
            if isinstance(updated, (
                int,
                float,
            )):
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
        key: str
        value: object
        values: dict[str, str] = {
            key: _display_text(value)
            for key, value in display.items()
        }
        if len(values.get('name', '')) > DIALOG_NAME_WIDTH:
            prefix_width: int = (
                DIALOG_NAME_WIDTH - len(DIALOG_NAME_ELLIPSIS)
            )
            values['name'] = (
                values['name'][:prefix_width] + DIALOG_NAME_ELLIPSIS
            )
        displays.append(values)

    context: list[str] = [
        'sort-by: "last-update-time" (newest first)',
    ]
    row: dict[str, str]
    cwd_values: set[str] = {
        row.get('cwd', '') for row in displays
    }
    harness_values: set[str] = {
        row.get('harness', '') for row in displays
    }
    uniform_cwd: bool = (
        show_cwd
        and len(cwd_values) == 1
        and bool(next(iter(cwd_values)))
    )
    uniform_harness: bool = (
        len(harness_values) == 1
        and bool(next(iter(harness_values)))
    )
    if uniform_cwd:
        context.append('CWD=' + next(iter(cwd_values)))
    if uniform_harness:
        context.append('HARNESS=' + next(iter(harness_values)))

    columns: list[tuple[str, str]] = []
    if not uniform_harness:
        columns.append((
            'harness',
            'HARNESS',
        ))
    columns.extend([
        (
            'name',
            'NAME',
        ),
        (
            'wkt',
            'WKT',
        ),
    ])
    if show_did:
        columns.append((
            'id',
            'DIALOG ID',
        ))
    if show_timestamps:
        columns.append((
            'updated',
            'UPDATED (UTC)',
        ))
    if (
        show_cwd
        and
        not uniform_cwd
    ):
        columns.append((
            'cwd',
            'CWD',
        ))
    key: str
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
        return (
            '\n'.join(context) + '\n'
            '\n' + table
        )
    return table


def main(argv: list[str]|None = None) -> int:
    '''
    Dispatch listing, resume and indexing from every CLI entry point.

    - Installed commands, source aliases, python -m aiskillz and the
      Xontrib use this dispatcher.
    - `index` delegates to index_main(); `resume` to resume_main().
      Spell a directory literally named index as ./index.
    - Normal listing applies filters through dialogs.list_dialogs(),
      then prints either exact JSON or format_dialog_table() output.
    - Color only eligible terminal headers/context labels.
    - `/open-wkt` may invoke the canonical source script without pip.
    - Return zero on success; argparse/store errors exit nonzero.

    '''
    if argv is None:
        argv = sys.argv[1:]

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
            'codex',
            'cx',
            'opencode',
            'oc',
            'claude',
            'cld',
            'all',
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
    repo: str|None = args.repo
    if args.all_repos:
        repo = None

    harness: str|None = args.harness
    if harness == 'all':
        harness = None

    try:
        sessions: list[dict] = dialogs.list_dialogs(
            repo,
            harness,
            all=args.all,
            all_sources=args.all_sources,
        )

        output: str
        if args.json:
            output = json.dumps(sessions, indent=2)
        else:
            output = format_dialog_table(
                sessions,
                show_timestamps=args.timestamps,
                show_did=args.did,
            )

    except (
        OSError,
        ValueError,
        sqlite3.Error,
    ) as error:
        parser.exit(1, f'ai.dlogs: {error}\n')

    if not args.json and _terminal_color_enabled():
        context: str
        context_separator: str
        table: str
        (
            context,
            context_separator,
            table,
        ) = output.partition(
            '\n'
            '\n',
        )
        if not context_separator:
            table = context
            context = ''
        header: str
        separator: str
        body: str
        (
            header,
            separator,
            body,
        ) = table.partition('\n')
        table = f'\x1b[90m{header}\x1b[0m{separator}{body}'
        if context_separator:
            colored: list[str] = []
            line: str
            for line in context.splitlines():
                label: str
                separator: str
                value: str
                delimiter: str = '='
                if line.startswith('sort-by: '):
                    delimiter = ': '

                (
                    label,
                    separator,
                    value,
                ) = line.partition(delimiter)
                colored.append(
                    f'\x1b[90m{label}{separator}\x1b[0m{value}'
                )

            context = '\n'.join(colored)

        output = table
        if context_separator:
            output = context + context_separator + table

    print(output)
    return 0


def resume_main(argv: list[str]|None = None) -> int:
    '''
    Resolve one dialog, then preview or launch its harness command.

    - Use resume_target() for selector/cwd resolution before probing.
    - For Codex, probe help for --no-daemon and add it only if
      supported.
    - Print resolution warnings without blocking a valid saved-cwd
      fallback merely because optional WKT metadata is unavailable.
    - --dry-run prints exact argv/cwd and launches no dialog; it
      still performs the capability probe needed to construct that
      argv.
    - Otherwise check the executable, inherit the terminal, run argv
      directly in the resolved cwd and return the harness exit
      status.
    - Surface selection, store and process failures as CLI
      diagnostics.

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
            'codex',
            'cx',
            'opencode',
            'oc',
            'claude',
            'cld',
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
        if (
            target['harness'] == 'codex'
            and
            codex_supports_no_daemon()
        ):
            target['argv'].insert(2, '--no-daemon')
        warning: str
        for warning in target.get('warnings', []):
            print('ai.resume: Warning: ' + warning, file=sys.stderr)
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
    Preview, apply or explicitly record dialog/WKT metadata.

    Preview (default):
    - Call preview_wkt_relations(), save its proposal JSON and
      display WKT matches, exact-ID resume commands, counts and
      warnings.
    - Show an apply command only when entries exist. --json exposes
      the full proposal, saved path and digest instead of terminal
      text.
    - Render one shared Xonsh/POSIX command when quoting permits it;
      hide the repetitive legacy-owner marker only in terminal rows.

    Writes (explicit):
    - --apply requires a digest; --choose resolves ambiguous
      proposals.
    - --record resolves an exact ID or unique name within one
      harness, across directories and including archived/other source
      records.
    - Reject invalid mode combinations before calling the writer.
    - Print the changed-relation count; report failures with context
      and exit nonzero. These modes do not launch/resume a harness.

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
        '--record', nargs=2, metavar=(
            'HARNESS',
            'NAME_OR_ID',
        ),
        help='record a WKT relation for a saved dialog name or ID',
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
            harness: str
            selector: str
            harness, selector = args.record
            canonical: str = canonical_harness(harness)
            harness_label: str = repr(harness)
            if harness != canonical:
                harness_label += f' ({canonical})'
            records: list[dict] = dialogs.list_dialogs(
                path=None, harness=canonical, all_sources=True,
                include_archived=True,
            )
            row: dict
            matches: list[dict] = [
                row for row in records if row['id'] == selector
            ]
            if not matches:
                matches = [
                    row for row in records
                    if row['name'] == selector
                ]
            if not matches:
                raise ValueError(
                    f'No saved dialog with name or ID {selector!r} '
                    f'for harness {harness_label}\n'
                    f'Check --record HARNESS and the dialog '
                    f'name or ID'
                )

            if len(matches) > 1:
                ids: str = ', '.join(row['id'] for row in matches)
                raise ValueError(
                    f'Dialog name {selector!r} is ambiguous '
                    f'for harness {harness_label}\n'
                    f'Pass an exact ID: {ids}'
                )

            selected: dict = matches[0]
            changed = dialogs.record_wkt_relation(
                args.repo, selected['harness'], selected['id'],
                args.worktree,
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
                    'path': str(path),
                    'sha256': digest,
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
                    status_label: str = (
                        f'{status:<{_INDEX_STATUS_WIDTH}}'
                    )
                    print(
                        _grey_label(status_label, color),
                        _highlight(label, _ANSI_CYAN, color),
                    )
                    if entry['name'] != '(metadata)':
                        name: str = entry['name']
                        resume_commands: list[tuple[str, str]] = (
                            _shell_commands(
                                'Resume',
                                [
                                    'ai.resume',
                                    name,
                                    '-a',
                                    '-b',
                                    harness,
                                    '--id',
                                    did,
                                ],
                                f'ai.resume @({name!r}) '
                                f'-a -b {harness} --id @({did!r})',
                            )
                        )
                        resume_label: str
                        resume_command: str
                        for (
                            resume_label,
                            resume_command,
                        ) in resume_commands:
                            print(
                                _grey_label(resume_label, color),
                                resume_command,
                            )

                    candidate: dict
                    for candidate in entry['candidates']:
                        target: str = json.dumps(
                            candidate['worktree'],
                        )
                        hidden_evidence: str = (
                            'legacy-owner-matching-dialog-id'
                        )
                        item: str
                        evidence: str = ', '.join(
                            item for item in candidate['evidence']
                            if item != hidden_evidence
                        )
                        detail: str = ''
                        if evidence:
                            detail = f' [{evidence}]'
                        colored_target: str = _highlight(
                            target, _ANSI_BLUE, color,
                        )
                        print('  ' + colored_target + detail)

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
                    apply_commands: list[tuple[str, str]] = (
                        _shell_commands(
                            'Apply',
                            [
                                'ai.dlogs',
                                'index',
                                repo,
                                '--apply',
                                preview_path,
                                '--sha256',
                                digest,
                            ],
                            f'ai.dlogs index @({repo!r}) '
                            f'--apply @({preview_path!r}) '
                            f'--sha256 {digest}',
                        )
                    )
                    apply_label: str
                    apply_command: str
                    for (
                        apply_label,
                        apply_command,
                    ) in apply_commands:
                        print(
                            _grey_label(apply_label, color),
                            apply_command,
                        )

    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        sqlite3.Error,
    ) as error:
        parser.exit(1, 'ai.dlogs index: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
