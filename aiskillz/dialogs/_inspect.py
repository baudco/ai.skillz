# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Recover structured worktree observations for index previews.

`WktIndexer.suggest()` first selects dialogs belonging to the
target repository, then passes their metadata to `observations()`.
This module reads those dialogs' local history and returns sets of
paths keyed by `(harness, id)`. The indexer matches them to
registered worktrees and presents candidates for human confirmation.

Codex JSONL tool inputs, Claude JSONL cwd fields and OpenCode message
`path.cwd` values can reveal a worktree even when a dialog's saved
cwd still names the main checkout. These observations describe
historical or requested directories, not successful execution or live
location.

No prompt text or shell-command string is interpreted, no command is
run, and no harness log is modified. Ordinary `list_dialogs()` and
`get_dialog()` do not invoke this additional history scan.

'''

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator, TextIO


def structured_paths(event: dict) -> Iterator[str]:
    '''
    Yield cwd/workdir strings from one supported structured event.

    `jsonl_paths()` supplies Codex/Claude objects; `observations()`
    also supplies decoded OpenCode message data. Inspect the event
    and its optional payload, recognized Codex tool-call arguments
    and OpenCode `path.cwd`. Unknown formats simply produce no
    observations.

    Tool inputs describe a requested directory even if the tool
    failed. This extractor neither validates Git roots nor chooses a
    worktree; `WktIndexer.suggest()` does that and preserves
    ambiguity. Free-form prompts and command text are never treated
    as path evidence.

    '''
    blocks: list[dict] = [event]
    payload: object = event.get('payload')
    if isinstance(payload, dict):
        blocks.append(payload)
    block: dict
    for block in blocks:
        field: str
        for field in ('cwd', 'workdir'):
            value: object = block.get(field)
            if isinstance(value, str):
                yield value
        if block.get('type') == 'function_call':
            if block.get('name', '').rsplit('.', 1)[-1] not in (
                'exec_command', 'shell_command', 'shell',
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
                for field in ('cwd', 'workdir'):
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
    Stream structured paths from one selected dialog's JSONL log.

    `observations()` chooses files by dialog ID before calling this
    reader. Ignore malformed/partial JSON lines, non-object records
    and records whose explicit `sessionId` disagrees with
    `dialog_id`. Delegate extraction to `structured_paths()` and
    yield only strings.

    The caller gathers paths and reports file-read failures as
    preview warnings. No raw events, prompt text or titles are
    returned here; this is historical evidence for indexing, not
    transcript export.

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
    Collect historical directory observations for selected dialogs.

    `WktIndexer.suggest()` passes repository-scoped
    `list_dialogs()` records. Return a mapping from `(harness, id)`
    to observed path strings; the caller matches these against its
    live worktree inventory. Respect `CODEX_HOME`,
    `CLAUDE_CONFIG_DIR` and `OPENCODE_DATA_DIR` (or XDG).

    Scan matching Codex rollouts and top-level Claude logs, then
    query OpenCode message rows read-only for selected IDs.
    Missing/pruned logs and absent message tables yield no evidence.
    File/SQLite read failures append to the caller-owned `warnings`
    list so a preview can report partial coverage. This does not
    broaden dialog source eligibility or persist an observation
    cache.

    '''
    result: dict[tuple[str, str], set[str]] = {}
    row: dict
    selected: set[tuple[str, str]] = {
        (row['harness'], row['id']) for row in dialogs
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
        ('codex', codex / 'sessions', '**/*.jsonl'),
        ('claude', claude / 'projects', '*/*.jsonl'),
    ):
        ids: set[str] = {
            row['id'] for row in dialogs if row['harness'] == harness
        }
        path: Path
        for path in base.glob(pattern):
            # Codex rollout basenames end in the full thread UUID.
            did: str = path.stem[-36:] if harness == 'codex' else (
                path.stem
            )
            if did not in ids:
                continue
            try:
                result.setdefault((harness, did), set()).update(
                    jsonl_paths(path, did),
                )
            except OSError:
                warnings.append(
                    'Could not read transcript: ' + str(path),
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
    for database in (oc / 'opencode.db', oc / 'opencode-stable.db'):
        if not oc_ids:
            break
        if not database.is_file():
            continue
        try:
            connection: sqlite3.Connection
            with closing(sqlite3.connect(
                database.as_uri() + '?mode=ro', uri=True, timeout=2,
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
                                ('opencode', did), set(),
                            ).update(structured_paths(event))
        except sqlite3.Error:
            warnings.append(
                'Could not read message cwd: ' + str(database),
            )
    return result
