# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Extract historical WKT directory evidence for index previews.

- WktIndexer.suggest() scopes dialogs to the repository before
  calling observations(); results are path sets by `(harness, id)`.
- Inspect Codex structured tool inputs, Claude JSONL cwd fields and
  OpenCode message path.cwd even when saved cwd still names main.
- Requested/historical directories do not prove successful execution
  or an agent's current cwd. The indexer verifies Git scope later.
- Never interpret prompt text or shell-command strings, execute a
  command or modify a harness log.
- Normal list_dialogs()/get_dialog() calls do not run this scan.

'''

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from collections.abc import Iterator
from typing import TextIO


# Codex rollout filenames end with a UUID, not a truncated display
# name.
_CODEX_ROLLOUT_ID_LENGTH: int = 36
_SQLITE_BUSY_TIMEOUT_SECONDS: int = 2


def structured_paths(event: dict) -> Iterator[str]:
    '''
    Extract recorded directories from one harness log/message object.

    - `jsonl_paths()` supplies Codex/Claude events; `observations()`
      also supplies decoded OpenCode message data.
    - Read cwd/workdir on the event and optional payload, recognized
      Codex shell-tool arguments, and OpenCode path.cwd.
    - Ignore unknown shapes and invalid tool-argument JSON.
    - A tool input is a requested directory, not proof the tool ran.
      `WktIndexer.suggest()` checks Git scope and preserves
      ambiguity.
    - Never interpret prompt text or shell command strings as
      evidence.

    '''
    blocks: list[dict] = [event]
    payload: object = event.get('payload')
    if isinstance(payload, dict):
        blocks.append(payload)
    block: dict
    for block in blocks:
        field: str
        for field in (
            'cwd',
            'workdir',
        ):
            value: object = block.get(field)
            if isinstance(value, str):
                yield value
        if block.get('type') == 'function_call':
            name: object = block.get('name')
            if not isinstance(name, str):
                continue
            if name.rsplit('.', 1)[-1] not in (
                'exec_command',
                'shell_command',
                'shell',
            ):
                continue
            try:
                args: dict = json.loads(block.get('arguments', '{}'))
            except (
                ValueError,
                TypeError,
            ):
                continue
            if isinstance(args, dict):
                for field in (
                    'cwd',
                    'workdir',
                ):
                    value = args.get(field)
                    if isinstance(value, str):
                        yield value
        path: object = block.get('path')
        if isinstance(path, dict):
            value = path.get('cwd')
            if isinstance(value, str):
                yield value


def jsonl_paths(path: Path, dialog_id: str) -> Iterator[str]:
    '''
    Stream directory evidence from a selected dialog's JSONL file.

    - `observations()` chooses the file by ID before calling this
      reader.
    - Skip partial/malformed JSON, non-object events and explicit
      sessionId values that disagree with `dialog_id`.
    - Delegate recognized fields to `structured_paths()`.
    - Yield strings only; titles and prompt bodies are not exported.
    - Read/decode failures propagate to `observations()`, which owns
      preview warnings. This helper neither records nor applies a
      WKT.

    '''
    stream: TextIO
    with path.open() as stream:
        line: str
        for line in stream:
            try:
                event: dict = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get('sessionId', dialog_id) != dialog_id:
                continue
            yield from structured_paths(event)


def observations(
    dialogs: list[dict],
    warnings: list[str],
) -> dict[tuple[str, str], set[str]]:
    '''
    Collect directory evidence for repository-scoped dialogs.

    - `WktIndexer.suggest()` supplies selected metadata and a mutable
      `warnings` list. Return `{(harness, id): set(observed_paths)}`.
    - Select Codex rollouts and top-level Claude logs by dialog ID;
      query OpenCode message rows read-only for the selected IDs.
    - Honor CODEX_HOME, CLAUDE_CONFIG_DIR and OPENCODE_DATA_DIR/XDG.
    - Missing/pruned logs and missing message tables add no evidence.
      File/SQLite failures append warnings about partial coverage.
    - Return historical/requested paths, not live agent locations;
      the indexer separately checks them against Git registration.
    - Do not change source eligibility, persist a cache or modify
      logs.

    '''
    result: dict[tuple[str, str], set[str]] = {}
    row: dict
    selected: set[tuple[str, str]] = {
        (
            row['harness'],
            row['id'],
        ) for row in dialogs
    }
    codex: Path = Path(os.environ.get(
        'CODEX_HOME', str(Path.home() / '.codex'),
    )).expanduser().resolve()
    claude: Path = Path(os.environ.get(
        'CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'),
    )).expanduser().resolve()
    harness: str
    base: Path
    pattern: str
    for (
        harness,
        base,
        pattern,
    ) in (
        (
            'codex',
            codex / 'sessions',
            '**/*.jsonl',
        ),
        (
            'claude',
            claude / 'projects',
            '*/*.jsonl',
        ),
    ):
        ids: set[str] = {
            row['id'] for row in dialogs if row['harness'] == harness
        }
        path: Path
        for path in base.glob(pattern):
            # Codex rollout basenames end in the full thread UUID.
            did: str = path.stem
            if harness == 'codex':
                did = path.stem[-_CODEX_ROLLOUT_ID_LENGTH:]
            if did not in ids:
                continue
            try:
                result.setdefault((
                    harness,
                    did,
                ), set()).update(
                    jsonl_paths(path, did),
                )
            except OSError as error:
                path_text: str = str(path)
                warnings.append(
                    f'Could not read transcript: {path_text!r}; '
                    f'{error}',
                )
    data: Path = Path(os.environ.get(
        'XDG_DATA_HOME', str(Path.home() / '.local/share'),
    )).expanduser()
    oc: Path = Path(os.environ.get(
        'OPENCODE_DATA_DIR', str(data / 'opencode'),
    )).expanduser().resolve()
    database: Path
    did: str
    oc_ids: list[str] = [
        did for harness, did in selected if harness == 'opencode'
    ]
    for database in (
        oc / 'opencode.db',
        oc / 'opencode-stable.db',
    ):
        if not oc_ids:
            break
        if not database.is_file():
            continue
        try:
            connection: sqlite3.Connection
            with closing(sqlite3.connect(
                database.as_uri() + '?mode=ro',
                uri=True,
                timeout=_SQLITE_BUSY_TIMEOUT_SECONDS,
            )) as connection:
                # OpenCode messages carry path.cwd in JSON data.
                row: tuple
                tables: set[str] = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table'",
                    )
                }
                if 'message' not in tables:
                    continue
                did: str
                for did in oc_ids:
                    raw: str
                    for (raw,) in connection.execute(
                        'SELECT data FROM message '
                        'WHERE session_id=?',
                        (did,),
                    ):
                        try:
                            event: dict = json.loads(raw)
                        except ValueError:
                            continue
                        if isinstance(event, dict):
                            result.setdefault(
                                (
                                    'opencode',
                                    did,
                                ), set(),
                            ).update(structured_paths(event))
        except sqlite3.Error as error:
            database_text: str = str(database)
            warnings.append(
                f'Could not read message cwd: {database_text!r}; '
                f'{error}',
            )
    return result
