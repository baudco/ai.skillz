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
from ._display import (
    DIALOG_NAME_WIDTH,
    DIALOG_NAME_ELLIPSIS,
)
from .wkt import WktLookup


# Help is a local capability probe, not a model turn. Bound a stuck
# CLI so interactive resume can fall back to its ordinary command
# promptly.
_CODEX_HELP_TIMEOUT_SECONDS: int = 5


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
            timeout=_CODEX_HELP_TIMEOUT_SECONDS,
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

    Selection:
    - Match an exact ID first, then an exact saved name.
    - Search saved cwd in `repo`; `all_repos=True` widens that scope.
    - Also accept a unique name shortened by ai.dlogs's display
      limit.
    - Never break ties by recency. `harness` and `dialog_id` narrow
      ambiguous names or cross-harness IDs.

    Launch directory:
    - Explicit `cwd`, then one available registered WKT, then saved
      cwd.
    - Unavailable, ambiguous or unreadable WKT metadata adds
      warnings;
      indexing alone never prevents resume.
    - An unusable final directory requires an explicit `cwd`
      override.
    - Orchestrating callers validate and supply their intended repo;
      an interactive fallback does not authorize another launch
      context.

    Process boundary:
    - Return argv, saved cwd, launch cwd and optional warning
      strings.
    - Never probe or launch a harness. `codex_no_daemon` is a
      capability
      observation supplied by the caller; `environ` selects metadata
      directories just as it does for `list_dialogs()`.

    '''
    if (
        not isinstance(name, str)
        or
        not name
    ):
        raise ValueError(
            f'NAME_OR_ID must be a nonempty string; got {name!r}'
        )
    scope: str|None = repo
    if all_repos:
        scope = None

    records: list[dict] = dialogs.list_dialogs(
        path=scope,
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
        len(name) == DIALOG_NAME_WIDTH
        and
        name.endswith(DIALOG_NAME_ELLIPSIS)
    ):
        # Listing truncates presentation, not identity. Accept a
        # pasted table value only if the retained prefix resolves
        # uniquely.
        prefix: str = name[:-len(DIALOG_NAME_ELLIPSIS)]
        matches = [
            record for record in records
            if record['name'].startswith(prefix)
        ]

    if dialog_id is not None:
        matches = [
            record for record in matches
            if record['id'] == dialog_id
        ]

    if not matches:
        raise ValueError(
            f'No dialog matching {name!r} in the selected scope; '
            f'harness={harness!r}, repo={scope!r}, '
            f'dialog_id={dialog_id!r}'
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
            f'Dialog selector {name!r} is ambiguous; '
            f'use --id, -b, or --repo: {choices}'
        )

    selected: dict = matches[0]
    did: str = selected['id']
    provider: str = selected['harness']
    dialog_name: str = selected['name']
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
        raise ValueError(
            f'Dialog ID is invalid for a harness CLI: {did!r}; '
            f'harness={provider!r}, name={dialog_name!r}'
        )

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
        raise ValueError(
            f'Unsupported harness: {provider!r}; '
            f'dialog={dialog_name!r}, id={did!r}'
        )

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
            f'Dialog has no saved cwd; use --cwd: '
            f'name={dialog_name!r}, id={did!r}, '
            f'harness={provider!r}, saved_cwd={saved!r}'
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
                    recorded_path: str = str(recorded_cwd)
                    notices.append(
                        f'Recorded WKT directory is missing: '
                        f'{recorded_path!r}; '
                        f'dialog={dialog_name!r}, id={did!r}'
                    )
            elif len(roots) > 1:
                notices.append(
                    f'Several WKTs match this dialog; '
                    f'using saved cwd: name={dialog_name!r}, '
                    f'id={did!r}, roots={roots!r}'
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
            notices.append(
                f'Cannot read WKT metadata: {error}; '
                f'dialog={dialog_name!r}, id={did!r}, '
                f'harness={provider!r}'
            )
        if notices:
            launch_cwd: str = str(directory)
            notices.append(f'Resuming in saved cwd: {launch_cwd!r}')

    if not directory.is_dir():
        invalid_directory: str = str(directory)
        raise ValueError(
            f'Launch directory is missing: {invalid_directory!r}; '
            f'dialog={dialog_name!r}, id={did!r}, '
            f'harness={provider!r}\n'
            f'Use --cwd to choose an existing directory.'
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
