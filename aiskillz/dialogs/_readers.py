# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Offline readers for harness-owned session metadata.

'''

from contextlib import closing
import json
from os import stat_result
from typing import BinaryIO
from pathlib import Path
import re
import sqlite3


# SQLite readers wait briefly for an index writer, never for a model
# turn.
_SQLITE_BUSY_TIMEOUT_SECONDS: int = 2
_MILLISECONDS_PER_SECOND: int = 1000
# Only the untitled-dialog fallback uses prompt text, bounded for
# display.
_CLAUDE_PROMPT_FALLBACK_LENGTH: int = 120


def codex_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
    include_archived: bool = False,
) -> list[dict]:
    '''
    Read Codex saved-dialog metadata from its local SQLite index.

    - Isolate the private `state_5.sqlite`/threads schema in this
      reader.
    - Prefer a saved name; older schemas fall back to title.
    - Filter exact saved cwd, source and archive state in SQL.
    - `include_archived` supports explicit historical WKT recording.
    - Use a read-only connection with a bounded busy timeout; close
      it before returning. Missing/unsupported indexes raise visibly.

    '''
    database: Path = home / 'state_5.sqlite'
    if not database.is_file():
        raise ValueError(
            f'Codex session index not found: {database}',
        )
    connection: sqlite3.Connection
    with closing(
        sqlite3.connect(
            database.as_uri() + '?mode=ro',
            uri=True,
            timeout=_SQLITE_BUSY_TIMEOUT_SECONDS,
        )
    ) as connection:
        connection.row_factory = sqlite3.Row
        row: sqlite3.Row
        columns: set[str] = {
            row['name']
            for row in connection.execute(
                'PRAGMA table_info(threads)',
            )
        }
        required: set[str] = {
            'id',
            'cwd',
            'title',
            'source',
            'updated_at',
            'archived',
        }
        if not required.issubset(columns):
            missing: list[str] = sorted(required - columns)
            database_text: str = str(database)
            raise ValueError(
                f'Unsupported Codex threads schema: '
                f'database={database_text!r}, missing={missing!r}'
            )
        name: str = "COALESCE(NULLIF(title, ''), '(untitled)')"
        if 'name' in columns:
            name = (
                "COALESCE(NULLIF(name, ''), NULLIF(title, ''), "
                "'(untitled)')"
            )
        query: str = (
            f'SELECT id, {name} AS name, cwd, source, updated_at, '
            f'archived '
            f'FROM threads WHERE 1 = 1'
        )
        if not include_archived:
            query += ' AND archived = 0'
        parameters: list[str] = []
        if cwd is not None:
            query += ' AND cwd = ?'
            parameters.append(cwd)
        if not all_sources:
            query += " AND source IN ('cli', 'vscode')"
        query += ' ORDER BY updated_at DESC, id DESC'
        row: sqlite3.Row
        return [
            {
                'harness': 'codex',
                **dict(row),
                'archived': bool(row['archived']),
            }
            for row in connection.execute(query, parameters)
        ]


def opencode_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
    include_archived: bool = False,
) -> list[dict]:
    '''
    Read OpenCode dialogs from SQLite or its older JSON layout.

    - Prefer available opencode.db/opencode-stable.db databases; keep
      the newest row per dialog ID across them.
    - Use storage/session JSON only when neither database exists.
    - Filter exact saved cwd, child sources and archive state in both
      formats. `include_archived` widens manual WKT recording.
    - Convert millisecond timestamps to the public seconds
      convention.
    - Skip malformed legacy records; database and file-read errors
      propagate rather than pretending a store is empty.
    - All connections are read only and bounded by the busy timeout.

    '''
    rows: dict[str, dict] = {}
    p: Path
    databases: list[Path] = [
        p
        for p in (
            home / 'opencode.db',
            home / 'opencode-stable.db',
        )
        if p.is_file()
    ]
    database: Path
    for database in databases:
        connection: sqlite3.Connection
        with closing(
            sqlite3.connect(
                database.as_uri() + '?mode=ro',
                uri=True,
                timeout=_SQLITE_BUSY_TIMEOUT_SECONDS,
            )
        ) as connection:
            connection.row_factory = sqlite3.Row
            query: str = (
                'SELECT id, title, directory, time_updated, '
                'time_archived '
                'FROM session WHERE 1 = 1'
            )
            if not include_archived:
                query += ' AND time_archived IS NULL'
            parameters: list[str] = []
            if cwd is not None:
                query += ' AND directory = ?'
                parameters.append(cwd)
            if not all_sources:
                query += ' AND parent_id IS NULL'
            row: sqlite3.Row
            for row in connection.execute(query, parameters):
                title: object = row['title']
                if (
                    not isinstance(title, str)
                    or
                    not title
                ):
                    title = '(untitled)'
                item: dict = {
                    'harness': 'opencode',
                    'id': row['id'],
                    'name': title,
                    'cwd': row['directory'],
                    'source': 'opencode',
                    'updated_at': (
                        row['time_updated']
                        / _MILLISECONDS_PER_SECOND
                    ),
                    'archived': row['time_archived'] is not None,
                }
                old: dict = rows.get(item['id'], {})
                if item['updated_at'] >= old.get('updated_at', 0):
                    rows[item['id']] = item

    if not databases:
        path: Path
        for path in (home / 'storage/session').glob('*/*.json'):
            try:
                entry: object = json.loads(
                    path.read_text(encoding='utf-8'),
                )

            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
            ):
                continue
            if not isinstance(entry, dict):
                continue
            dialog_id: object = entry.get('id')
            directory: object = entry.get('directory')
            timing: object = entry.get('time', {})
            if (
                not isinstance(dialog_id, str)
                or
                not dialog_id
                or
                not isinstance(directory, str)
                or
                not directory
                or
                not isinstance(timing, dict)
            ):
                continue
            updated: object = timing.get('updated', 0)
            if (
                not isinstance(updated, (
                    int,
                    float,
                ))
                or
                isinstance(updated, bool)
            ):
                continue
            if (
                cwd is not None
                and
                directory != cwd
            ):
                continue
            if (
                not all_sources
                and
                entry.get('parentID')
            ):
                continue
            if (
                not include_archived
                and
                timing.get('archived')
            ):
                continue
            title: object = entry.get('title')
            if (
                not isinstance(title, str)
                or
                not title
            ):
                title = '(untitled)'
            rows[dialog_id] = {
                'harness': 'opencode',
                'id': dialog_id,
                'name': title,
                'cwd': directory,
                'source': 'opencode',
                'updated_at': updated / _MILLISECONDS_PER_SECOND,
                'archived': bool(timing.get('archived')),
            }

    return list(rows.values())


def claude_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
    include_archived: bool = False,
) -> list[dict]:
    '''
    Read Claude dialog names and original cwd from indexes or logs.

    - Restrict folders by encoded cwd when requested, then verify
      each record's actual original directory before returning it.
    - Trust indexed metadata only while the index is at least as
      fresh as the log; otherwise scan that log for its current
      title.
    - Prefer custom/AI title, last prompt, summary, then a bounded
      first prompt fallback. Returned metadata does not contain
      transcripts.
    - Decode JSONL one record at a time; skip malformed/non-object
      rows so one corrupt event cannot hide later metadata.
    - Exclude subagent logs: their IDs are not standalone resume
      targets.
    - Archive state is unknown in this format. The shared
      archive/source parameters do not broaden Claude's
      standalone-dialog selection.

    '''
    projects: Path = home / 'projects'
    folders: list[Path] = list(projects.glob('*'))
    if cwd is not None:
        folders = [projects / re.sub(r'[^a-zA-Z0-9]', '-', cwd)]
    result: list[dict] = []
    folder: Path
    for folder in folders:
        index: Path = folder / 'sessions-index.json'
        index_text: str = str(index)
        entries: dict[str, dict] = {}
        if index.is_file():
            indexed: object = json.loads(index.read_text())
            if (
                not isinstance(indexed, dict)
                or
                not isinstance(indexed.get('entries'), list)
            ):
                raise ValueError(
                    f'Unsupported Claude sessions index: '
                    f'{index_text!r}'
                )
            item: object
            for item in indexed['entries']:
                if not isinstance(item, dict):
                    continue
                indexed_id: object = item.get('sessionId')
                if (
                    isinstance(indexed_id, str)
                    and
                    indexed_id
                ):
                    entries[indexed_id] = item
        paths: list[Path] = list(folder.glob('*.jsonl'))
        path: Path
        for path in paths:
            stat: stat_result = path.stat()
            entry: dict = entries.get(path.stem, {})
            name: str = ''
            owner: str = ''
            did: str = path.stem
            sidechain: bool = 'subagents' in path.parts
            if (
                entry
                and
                isinstance(entry.get('projectPath'), str)
                and
                index.stat().st_mtime >= stat.st_mtime
            ):
                project: object = entry.get('projectPath')
                if isinstance(project, str):
                    owner = project
                field: str
                for field in (
                    'customTitle',
                    'aiTitle',
                    'lastPrompt',
                    'summary',
                    'firstPrompt',
                ):
                    title: object = entry.get(field)
                    if (
                        isinstance(title, str)
                        and
                        title
                    ):
                        name = title
                        break
                sidechain = entry.get('isSidechain', sidechain)
            else:
                custom: str = ''
                summary: str = ''
                prompt: str = ''
                last_prompt: str = ''
                stream: BinaryIO
                with path.open('rb') as stream:
                    line: bytes
                    for line in stream:
                        try:
                            event: dict = json.loads(
                                line.decode('utf-8'),
                            )

                        except (
                            json.JSONDecodeError,
                            UnicodeDecodeError,
                        ):
                            # Isolate corrupt or partial log records.
                            continue

                        if not isinstance(event, dict):
                            continue
                        if not owner:
                            directory: object = event.get('cwd')
                            if isinstance(directory, str):
                                owner = directory

                        identity: object = event.get('sessionId')
                        if (
                            isinstance(identity, str)
                            and
                            identity
                        ):
                            did = identity
                        sidechain = (
                            sidechain
                            or bool(event.get('isSidechain'))
                        )
                        kind: str = event.get('type', '')
                        if kind == 'custom-title':
                            title: object = event.get('customTitle')
                            if isinstance(title, str):
                                custom = title
                        elif kind == 'ai-title':
                            title = event.get('aiTitle')
                            if isinstance(title, str):
                                custom = title
                        elif kind == 'last-prompt':
                            title = event.get('lastPrompt')
                            if isinstance(title, str):
                                last_prompt = title
                        elif kind == 'summary':
                            title = event.get('summary')
                            if isinstance(title, str):
                                summary = title
                        elif (
                            kind == 'user'
                            and
                            not prompt
                        ):
                            message: object = event.get('message')
                            content: object = ''
                            if isinstance(message, dict):
                                content = message.get('content', '')
                            if isinstance(content, str):
                                prompt = content[
                                    :_CLAUDE_PROMPT_FALLBACK_LENGTH
                                ]

                name = (
                    custom
                    or last_prompt
                    or summary
                    or prompt
                )

            if (
                cwd is not None
                and
                owner != cwd
            ):
                continue
            if sidechain:
                # Claude subagent logs are not standalone resume IDs.
                continue
            result.append(
                {
                    'harness': 'claude',
                    'id': did,
                    'name': name or '(untitled)',
                    'cwd': owner,
                    'source': 'claude',
                    'updated_at': stat.st_mtime,
                }
            )

    return result
