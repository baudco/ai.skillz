# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Resolve a dialog name or ID to a harness command and directory.

`cli.resume_main()` selects a dialog through `dialogs.list_dialogs()`
and calls `resume_target()` before launching a child process. The
worktree lookup is shared with `ai.dlogs`, so an active recorded WKT
can replace a harness's older saved cwd. Resolution does not start
a harness; the explicit capability probe is a separate operation.
WKT indexing is optional metadata, never a prerequisite for resume.
Lookup failures warn and use saved cwd; only an unusable launch
directory requires the caller to provide --cwd.

'''

from pathlib import Path
from collections.abc import Mapping
import re
import subprocess

from . import dialogs
from .wkt import WktLookup


def codex_supports_no_daemon() -> bool:
    '''
    Check whether this Codex CLI accepts --no-daemon on resume.

    The CLI probes the installed command rather than a
    version string because package layouts can differ. A missing,
    failed, or unresponsive CLI keeps the older resume argv; the
    eventual launch reports any executable failure to the caller.

    '''
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            [
                'codex',
                'resume',
                '--help',
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return False
    return (
        result.returncode == 0
        and re.search(
            r'(?m)^\s*--no-daemon(?:\s|$)',
            result.stdout + '\n' + result.stderr,
        ) is not None
    )


def resume_target(
    name: str,
    repo: str = '.',
    harness: str|None = None,
    all_repos: bool = False,
    dialog_id: str|None = None,
    cwd: str|None = None,
    *,
    codex_no_daemon: bool = False,
    environ: Mapping[str, str]|None = None,
) -> dict:
    '''
    Return one dialog's harness argv and launch directory.

    Interpret `name` as an exact ID first, then as a saved name.
    Search the current directory by default; `all_repos=True`
    widens the saved-cwd search for either selector. Also accept a
    unique 36-character name shortened by `ai.dlogs`. Never pick
    duplicate IDs or names by recency; `dialog_id`, `harness`, and
    `repo` let the caller narrow them. Prefer a registered WKT
    relation from `WktLookup.roots()`. An explicit cwd overrides it.
    Unavailable, ambiguous or unreadable WKT metadata falls back to
    saved cwd with diagnostic strings in the returned `warnings`.
    No harness starts until a caller executes the returned argv.
    `codex_no_daemon` supplies a previously observed capability;
    resolution never probes a harness. Task-driven callers validate
    the intended repository and pass explicit cwd to prevent WKT
    metadata from choosing another directory.
    `environ` selects the same harness stores as discovery APIs.

    '''
    if (
        not isinstance(name, str)
        or
        not name
    ):
        raise ValueError('NAME_OR_ID must be a nonempty string')
    records: list[dict] = dialogs.list_dialogs(
        path=None if all_repos else repo,
        harness=harness,
        environ=environ,
    )
    record: dict
    matches: list[dict] = [
        record for record in records
        if record['id'] == name
    ]
    if not matches:
        matches = [
            record for record in records
            if record['name'] == name
        ]
    if (
        not matches
        and
        len(name) == 36
        and
        name.endswith('…')
    ):
        matches = [
            record for record in records
            if record['name'].startswith(name[:35])
        ]

    if dialog_id is not None:
        matches = [
            record for record in matches
            if record['id'] == dialog_id
        ]
    if not matches:
        raise ValueError(
            'No dialog matching ' + repr(name) +
            ' in the selected scope'
        )
    if len(matches) > 1:
        row: dict
        options: list[str] = []
        for row in matches:
            backend: str = row['harness']
            matched_id: str = row['id']
            saved_cwd: str = row['cwd']
            options.append(f'{backend}:{matched_id} @ {saved_cwd}')
        choices: str = ', '.join(options)
        raise ValueError(
            'Dialog selector is ambiguous; use --id, -b, or --repo: '
            + choices
        )

    selected: dict = matches[0]
    did: str = selected['id']
    char: str
    if (
        not isinstance(did, str)
        or
        not did
        or
        did.startswith('-')
        or
        any(not char.isprintable() for char in did)
    ):
        raise ValueError('Dialog ID is invalid for a harness CLI')

    provider: str = selected['harness']
    commands: dict[str, list[str]] = {
        'codex': [
            'codex',
            'resume',
            did,
        ],
        'opencode': [
            'opencode',
            '--session',
            did,
        ],
        'claude': [
            'claude',
            '--resume',
            did,
        ],
    }
    if provider not in commands:
        raise ValueError('Unsupported harness: ' + provider)
    if (
        provider == 'codex'
        and
        codex_no_daemon
    ):
        commands['codex'] = [
            'codex',
            'resume',
            '--no-daemon',
            did,
        ]

    saved: str = selected.get('cwd', '')
    if (
        cwd is None
        and
        not saved
    ):
        raise ValueError(
            'Dialog has no saved cwd; use --cwd'
        )

    notices: list[str] = []
    if cwd is not None:
        directory: Path = Path(cwd).expanduser().resolve()
    else:
        directory = Path(saved).expanduser().resolve()
        lookup: WktLookup = WktLookup()
        try:
            roots: set[str] = lookup.roots(saved, provider, did)
            if len(roots) == 1:
                recorded_cwd: Path = Path(
                    next(iter(roots)),
                ).resolve()
                if recorded_cwd.is_dir():
                    directory = recorded_cwd
                else:
                    notices.append(
                        'Recorded WKT directory is missing: '
                        + repr(str(recorded_cwd))
                    )
            elif len(roots) > 1:
                notices.append(
                    'Several WKTs match this dialog; using saved cwd'
                )
            elif lookup.has_relation(saved, provider, did):
                recorded: set[str] = lookup.recorded_roots(
                    saved, provider, did,
                )
                path: str
                paths: str = ', '.join(
                    repr(path) for path in sorted(recorded)
                )
                notices.append(
                    f'Recorded WKT is no longer available: {paths}'
                )
        except (
            OSError,
            ValueError,
        ) as error:
            notices.append('Cannot read WKT metadata: ' + str(error))
        if notices:
            launch_cwd: str = str(directory)
            notices.append(f'Resuming in saved cwd: {launch_cwd!r}')

    if not directory.is_dir():
        raise ValueError(
            'Launch directory is missing: ' + str(directory)
            + '\nUse --cwd to choose an existing directory.'
        )
    target: dict = {
        'name': selected['name'],
        'id': did,
        'harness': provider,
        'cwd': str(directory),
        'saved_cwd': saved,
        'argv': commands[provider],
    }
    if notices:
        target['warnings'] = notices
    return target
