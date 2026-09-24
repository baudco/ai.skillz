# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Public dialog discovery and worktree-relation orchestration.

Workspace modules and the CLI call these functions. _readers supplies
harness metadata; _inspect extracts recorded directories from logs.
The wkt layer matches those directories to Git worktrees and persists
relations. Shell parsing and table formatting belong to cli.py.

'''

from collections import Counter
import os
from pathlib import Path
import sqlite3

from ..wkt import WktIndexer
from ._inspect import observations
from ._readers import (
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



def get_dialog(
    dialog_id: str,
    harness: str|None = None,
) -> dict|None:
    '''
    Resolve an opaque dialog ID to its harness metadata record.

    A launcher or workspace module that retained only an ID can call
    this to recover `harness`, `name`, saved `cwd`, `source` and
    `updated_at`. Prefer `list_dialogs()` when selecting many dialogs
    at once; this helper currently enumerates the selected readers
    via `list_dialogs(path=None, harness=harness)` and then matches
    the ID.

    `harness=None` searches all supported harnesses across
    directories; a canonical name or alias narrows that search.
    Default source and archive exclusions from `list_dialogs()` still
    apply. This returns metadata only, with no transcript, WKT
    enrichment or harness launch.

    Return `None` when no eligible record matches. Raise `ValueError`
    for an empty/non-string ID or cross-harness ambiguity; callers
    can resolve ambiguity by supplying the harness. Store errors
    propagate rather than masquerading as a missing dialog.

    '''
    if (
        not isinstance(dialog_id, str)
        or
        not dialog_id
    ):
        raise ValueError('dialog_id must be a nonempty string')
    row: dict
    matches: list[dict] = [
        row for row in list_dialogs(path=None, harness=harness)
        if row['id'] == dialog_id
    ]
    if len(matches) > 1:
        raise ValueError('Dialog ID is ambiguous; specify harness')
    return matches[0] if matches else None


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

def preview_wkt_relations(
    path: str = '.',
    logs: bool = True,
) -> dict:
    '''
    Find possible worktrees for this repository's existing dialogs.

    Called by ai.dlogs index before saving its proposal JSON file.
    Read each harness independently; report unreadable databases in
    the proposal's warnings. WktIndexer limits history reads to
    this repository, then matches those directories to Git worktrees.
    With logs=False only saved cwd and old owner metadata are used.

    '''
    dialogs: list[dict] = []
    warnings: list[str] = []
    harness: str
    for harness in ('codex', 'opencode', 'claude'):
        try:
            dialogs.extend(list_dialogs(path=None, harness=harness))
        except (
            OSError,
            ValueError,
            sqlite3.Error,
        ) as error:
            warnings.append(harness + ': ' + str(error))
    indexer: WktIndexer = WktIndexer(path)
    return indexer.suggest(
        dialogs, observations if logs else None, warnings,
    )
