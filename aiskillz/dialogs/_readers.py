# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Offline readers for harness-owned session metadata.

'''

from contextlib import closing
import json
from os import stat_result
from typing import TextIO
from pathlib import Path
import re
import sqlite3


def codex_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
) -> list[dict]:
    '''
    Read the Codex 0.153.2 session index without modifying it.

    The private state_5.sqlite schema is deliberately isolated here.
    Named sessions prefer `name`; older schemas fall back to `title`.

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
            timeout=2,
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
            raise ValueError('Unsupported Codex threads schema')
        name: str = "COALESCE(NULLIF(title, ''), '(untitled)')"
        if 'name' in columns:
            name = (
                "COALESCE(NULLIF(name, ''), NULLIF(title, ''), "
                "'(untitled)')"
            )
        query: str = (
            f'SELECT id, {name} AS name, cwd, source, updated_at '
            f'FROM threads WHERE archived = 0'
        )
        parameters: list[str] = []
        if cwd is not None:
            query += ' AND cwd = ?'
            parameters.append(cwd)
        if not all_sources:
            query += " AND source IN ('cli', 'vscode')"
        query += ' ORDER BY updated_at DESC, id DESC'
        row: sqlite3.Row
        return [
            {'harness': 'codex', **dict(row)}
            for row in connection.execute(query, parameters)
        ]


def opencode_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
) -> list[dict]:
    '''
    Read SQLite indexes, falling back to pre-SQLite session JSON.

    '''
    rows: dict[str, dict] = {}
    p: Path
    databases: list[Path] = [
        p
        for p in (home / 'opencode.db', home / 'opencode-stable.db')
        if p.is_file()
    ]
    database: Path
    for database in databases:
        connection: sqlite3.Connection
        with closing(
            sqlite3.connect(
                database.as_uri() + '?mode=ro',
                uri=True,
                timeout=2,
            )
        ) as connection:
            connection.row_factory = sqlite3.Row
            query: str = (
                'SELECT id, title, directory, time_updated '
                'FROM session WHERE time_archived IS NULL'
            )
            parameters: list[str] = []
            if cwd is not None:
                query += ' AND directory = ?'
                parameters.append(cwd)
            if not all_sources:
                query += ' AND parent_id IS NULL'
            row: sqlite3.Row
            for row in connection.execute(query, parameters):
                item: dict = {
                    'harness': 'opencode',
                    'id': row['id'],
                    'name': row['title'] or '(untitled)',
                    'cwd': row['directory'],
                    'source': 'opencode',
                    'updated_at': row['time_updated'] / 1000,
                }
                old: dict = rows.get(item['id'], {})
                if item['updated_at'] >= old.get('updated_at', 0):
                    rows[item['id']] = item
    if not databases:
        path: Path
        for path in (home / 'storage/session').glob('*/*.json'):
            entry: dict = json.loads(path.read_text())
            if (
                cwd is not None
                and
                entry.get('directory') != cwd
            ):
                continue
            if (
                not all_sources
                and
                entry.get('parentID')
            ):
                continue
            if entry.get('time', {}).get('archived'):
                continue
            rows[entry['id']] = {
                'harness': 'opencode',
                'id': entry['id'],
                'name': entry.get('title') or '(untitled)',
                'cwd': entry['directory'],
                'source': 'opencode',
                'updated_at': entry.get('time', {}).get('updated', 0)
                / 1000,
            }
    return list(rows.values())


def claude_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
) -> list[dict]:
    '''
    Read project indexes and logs, keeping exact cwd ownership.

    Indexed metadata is used only while at least as fresh as its log.
    Otherwise scan the log for current titles and the original cwd.
    No transcript text is returned beyond a fallback first-prompt
    name.

    '''
    projects: Path = home / 'projects'
    folders: list[Path] = list(projects.glob('*'))
    if cwd is not None:
        folders = [projects / re.sub(r'[^a-zA-Z0-9]', '-', cwd)]
    result: list[dict] = []
    folder: Path
    for folder in folders:
        index: Path = folder / 'sessions-index.json'
        entries: dict[str, dict] = {}
        if index.is_file():
            item: dict
            entries = {
                item['sessionId']: item
                for item in json.loads(index.read_text())['entries']
            }
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
                index.stat().st_mtime >= stat.st_mtime
            ):
                owner = entry.get('projectPath', '')
                name = (
                    entry.get('customTitle')
                    or
                    entry.get('aiTitle')
                    or
                    entry.get('lastPrompt')
                    or
                    entry.get('summary')
                    or
                    entry.get('firstPrompt')
                    or
                    ''
                )
                sidechain = entry.get('isSidechain', sidechain)
            else:
                custom: str = ''
                summary: str = ''
                prompt: str = ''
                last_prompt: str = ''
                stream: TextIO
                with path.open() as stream:
                    line: str
                    for line in stream:
                        try:
                            event: dict = json.loads(line)
                        except json.JSONDecodeError:
                            # Active logs may end in a partial line.
                            continue
                        if not owner:
                            owner = event.get('cwd', '')
                        if event.get('sessionId'):
                            did = event['sessionId']
                        sidechain = (
                            sidechain
                            or
                            bool(event.get('isSidechain'))
                        )
                        kind: str = event.get('type', '')
                        if kind == 'custom-title':
                            custom = event.get('customTitle', '')
                        elif kind == 'ai-title':
                            custom = event.get('aiTitle', '')
                        elif kind == 'last-prompt':
                            last_prompt = event.get('lastPrompt', '')
                        elif kind == 'summary':
                            summary = event.get('summary', '')
                        elif (
                            kind == 'user'
                            and
                            not prompt
                        ):
                            content: object = event.get(
                                'message', {},
                            ).get(
                                'content',
                                '',
                            )
                            if isinstance(content, str):
                                prompt = content[:120]
                name = (
                    custom
                    or
                    last_prompt
                    or
                    summary
                    or
                    prompt
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
