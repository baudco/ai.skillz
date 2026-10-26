# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Discover dialogs and coordinate the public WKT indexing workflow.

- dialogs._readers returns harness metadata; dialogs._inspect reads
  structured directory evidence only for explicit index previews.
- aiskillz.wkt matches evidence to Git WKTs and persists reviewed
  relations. The dialog API supplies its inputs, not another writer.
- cli.main() owns shell parsing; cli.format_dialog_table() owns
  terminal presentation. Library callers consume metadata records.

'''

from collections import Counter
import os
from collections.abc import Mapping
from typing import Protocol
from pathlib import Path
import sqlite3

from ..wkt import WktIndexer
from ..wkt._indexer import HistoryReader
from ._inspect import observations
from ._readers import (
    codex_sessions,
    opencode_sessions,
    claude_sessions,
)


class _SessionReader(Protocol):
    '''
    Describe the shared reader call used by `list_dialogs()`.

    - Each harness receives its root, exact cwd and source/archive
      flags.
    - Heterogeneous JSON/SQLite fields stay in dict records; listing
      fills the shared optional fields after the reader returns.

    '''

    def __call__(
        self,
        home: Path,
        cwd: str|None,
        all_sources: bool = False,
        include_archived: bool = False,
    ) -> list[dict]:
        '''
        Read one harness without changing its saved metadata.

        '''
        ...


def list_dialogs(
    path: str|Path|None = '.',
    harness: str|list[str]|None = None,
    all: bool = False,
    all_sources: bool = False,
    *,
    include_archived: bool = False,
    environ: Mapping[str, str]|None = None,
) -> list[dict]:
    '''
    List saved dialogs for library callers and `ai.dlogs`.

    Scope:
    - `path` filters saved cwd; None searches all directories.
    - `harness=None` selects all harnesses; names and alias lists
      narrow it.
    - `all=True` overrides both harness and directory filters.
    - `all_sources` includes child/noninteractive sources.
    - `include_archived` includes archived Codex/OpenCode rows, for
      example when explicitly recording a historical WKT relation.

    Results:
    - Deduplicate by `(harness, id)`, retaining the newest record.
    - Return newest first, with harness/ID tie-breakers.
    - Keep exact names. Unknown provider/model/archive fields stay
      None.

    Reader boundaries:
    - `environ` selects harness directories without changing
      os.environ; Xonsh completion supplies its current shell
      environment here.
    - Implicit all-harness discovery skips a missing Codex database;
      an explicit Codex selection reports it. Invalid stores raise.
    - Harness files are read only; this call neither scans transcript
      directories for WKT evidence nor records relations.

    '''
    environment: Mapping[str, str] = os.environ
    if environ is not None:
        environment = environ
    discover_all: bool = all or harness is None
    names: list[str]
    if discover_all:
        names = [
            'codex',
            'opencode',
            'claude',
        ]
    elif isinstance(harness, str):
        names = [harness]
    else:
        names = list(harness)
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
    unknown: set[str] = set(names) - {
        'codex',
        'opencode',
        'claude',
    }
    if unknown:
        invalid_names: list[str] = sorted(unknown)
        raise ValueError(f'Unknown harness: {invalid_names!r}')
    cwd: str|None = None
    if (
        not all
        and
        path is not None
    ):
        cwd = str(Path(path).expanduser().resolve())
    data: Path = Path(
        environment.get(
            'XDG_DATA_HOME',
            str(Path.home() / '.local/share'),
        )
    ).expanduser()
    homes: dict[str, Path] = {
        'codex': Path(
            environment.get(
                'CODEX_HOME',
                str(Path.home() / '.codex'),
            )
        ),
        'opencode': Path(
            environment.get(
                'OPENCODE_DATA_DIR',
                str(data / 'opencode'),
            )
        ),
        'claude': Path(
            environment.get(
                'CLAUDE_CONFIG_DIR',
                str(Path.home() / '.claude'),
            )
        ),
    }
    # All readers share the same positional and archive arguments.
    # Reader records contain heterogeneous JSON/SQLite fields.
    # Normalization below fills the public optional metadata fields.
    readers: dict[str, _SessionReader] = {
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
            discover_all
        ):
            continue
        records.extend(readers[name](
            home, cwd, all_sources or all,
            include_archived=include_archived,
        ))

    unique: dict[tuple[str, str], dict] = {}
    record: dict
    for record in sorted(records, key=lambda r: r['updated_at']):
        record.setdefault('provider', None)
        record.setdefault('model', None)
        record.setdefault('archived', None)
        unique[record['harness'], record['id']] = record
    return sorted(
        unique.values(),
        key=lambda r: (
            -r['updated_at'],
            r['harness'],
            r['id'],
        ),
    )


def get_dialog(
    dialog_id: str,
    harness: str|None = None,
    *,
    include_archived: bool = False,
    all_sources: bool = False,
    environ: Mapping[str, str]|None = None,
) -> dict|None:
    '''
    Find a dialog by its opaque ID, optionally within one harness.

    - Search eligible records through `list_dialogs(path=None)`; no
      transcript, WKT enrichment or process launch is involved.
    - `harness` accepts the same canonical names and aliases as
      listing.
    - Forward archive/source options and `environ` to those readers.
    - Return the exact metadata record or None when no eligible ID
      matches.
    - Raise ValueError for an invalid ID or a cross-harness
      collision; pass `harness` to disambiguate. Store errors
      propagate.
    - For many lookups, call `list_dialogs()` once and reuse its
      records.

    '''
    if (
        not isinstance(dialog_id, str)
        or
        not dialog_id
    ):
        raise ValueError(
            f'dialog_id must be a nonempty string; got {dialog_id!r}'
        )
    row: dict
    matches: list[dict] = [
        row for row in list_dialogs(
            path=None,
            harness=harness,
            include_archived=include_archived,
            all_sources=all_sources,
            environ=environ,
        )
        if row['id'] == dialog_id
    ]
    if len(matches) > 1:
        harnesses: list[str] = [row['harness'] for row in matches]
        raise ValueError(
            f'Dialog ID is ambiguous; specify harness: '
            f'id={dialog_id!r}, matches={harnesses!r}'
        )

    if matches:
        return matches[0]

    return None


def name2id(
    path: str|Path|None = '.',
    harness: str|list[str]|None = None,
    all: bool = False,
    all_sources: bool = False,
) -> dict[str, str]:
    '''
    Build a name-to-ID convenience mapping for dialog selection.

    - Use the same filters and order as `list_dialogs()`.
    - Suffix duplicate names with `[harness:id]` instead of dropping
      rows.
    - Append `#` when a generated label collides with an original
      name or a previously generated label.
    - Use `list_dialogs()` for exact names and harness-qualified
      identity; generated labels are presentation, not durable
      references.

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
    Suggest WKTs for existing dialogs in the selected repo.

    - `ai.dlogs index` calls this before saving a preview file.
    - Read each harness independently; collect store failures in the
      returned proposal's `warnings` instead of losing healthy
      harnesses.
    - `WktIndexer.suggest()` scopes history reads to this repository
      and matches observed directories to registered Git worktrees.
    - `logs=False` uses only saved cwd and owner metadata.
    - Return proposal data; no preview file or relation is written
      here.

    '''
    dialogs: list[dict] = []
    warnings: list[str] = []
    harness: str
    for harness in (
        'codex',
        'opencode',
        'claude',
    ):
        try:
            dialogs.extend(list_dialogs(path=None, harness=harness))
        except (
            OSError,
            ValueError,
            sqlite3.Error,
        ) as error:
            warnings.append(harness + ': ' + str(error))

    indexer: WktIndexer = WktIndexer(path)
    inspect_paths: HistoryReader|None = None
    if logs:
        inspect_paths = observations

    return indexer.suggest(dialogs, inspect_paths, warnings)
