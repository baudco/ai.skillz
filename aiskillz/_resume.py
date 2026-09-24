# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Resolve a dialog name to one harness command and working directory.

`cli.resume_main()` selects a dialog through `dialogs.list_dialogs()`
and calls `resume_target()` before launching a child process. The
worktree lookup is shared with `ai.dlogs`, so an active recorded WKT
can replace a harness's older saved cwd. This module does not spawn.

'''

from pathlib import Path

from . import dialogs
from .wkt import WktLookup


def resume_target(
    name: str,
    repo: str = '.',
    harness: str|None = None,
    all_repos: bool = False,
    dialog_id: str|None = None,
    cwd: str|None = None,
) -> dict:
    '''
    Return one dialog's harness argv and launch directory.

    Match the exact saved name in the current directory by default;
    `all_repos=True` widens the saved-cwd search. Also accept a
    unique 36-character name shortened by `ai.dlogs`. Never pick a
    duplicate name by recency; `dialog_id`, `harness`, and `repo`
    let the caller narrow it. Prefer one registered WKT relation
    from `WktLookup.roots()`. An explicit cwd overrides that lookup.
    No process starts until `cli.resume_main()` consumes the result.

    '''
    if (
        not isinstance(name, str)
        or
        not name
    ):
        raise ValueError('NAME must be a nonempty string')
    records: list[dict] = dialogs.list_dialogs(
        path=None if all_repos else repo,
        harness=harness,
    )
    record: dict
    matches: list[dict] = [
        record for record in records
        if (
            record['name'] == name
            and
            (dialog_id is None or record['id'] == dialog_id)
        )
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
            if (
                record['name'].startswith(name[:35])
                and
                (dialog_id is None or record['id'] == dialog_id)
            )
        ]
    if not matches:
        raise ValueError(
            'No dialog named ' + repr(name) +
            ' in the selected scope'
        )
    if len(matches) > 1:
        row: dict
        choices: str = ', '.join(
            f"{row['harness']}:{row['id']} @ {row['cwd']}"
            for row in matches
        )
        raise ValueError(
            'Dialog name is ambiguous; use --id, -b, or --repo: '
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
        'codex': ['codex', 'resume', did],
        'opencode': ['opencode', '--session', did],
        'claude': ['claude', '--resume', did],
    }
    if provider not in commands:
        raise ValueError('Unsupported harness: ' + provider)

    saved: str = selected.get('cwd', '')
    if (
        cwd is None
        and
        not saved
    ):
        raise ValueError(
            'Dialog has no saved cwd; use --cwd'
        )
    if cwd is not None:
        directory: Path = Path(cwd).expanduser().resolve()
    else:
        roots: set[str] = WktLookup().roots(
            saved, provider, did,
        )
        if len(roots) > 1:
            raise ValueError(
                'Several WKTs match this dialog; use --cwd'
            )
        directory = Path(
            next(iter(roots)) if roots else saved
        ).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(
            'Launch directory is missing: ' + str(directory)
        )
    return {
        'name': selected['name'],
        'id': did,
        'harness': provider,
        'cwd': str(directory),
        'argv': commands[provider],
    }
