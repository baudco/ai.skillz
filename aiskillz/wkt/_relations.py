# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Read and write shared dialog-to-WKT relation metadata.

- relations.json records dialog use; owner.json separately identifies
  the agent allowed to manage/remove a WKT under /open-wkt rules.
  Several dialogs may use the same tree under different owners.
- wkt._operations.record_wkt_relation() writes one known pair;
  apply_wkt_preview() writes pairs reviewed through ai.dlogs index.
  Both publish through update() and the same relations.json file.
- read()/list_wkt_relations() supply Python callers and CLI lookup.
- write.guard is an exclusive mkdir lock; writer.json holds this
  Python writer's PID. update() checks the digest under the guard,
  then atomically replaces relations.json.
- docs/aiskillz.md covers crash recovery and deferred KDL migration.

'''

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import TextIO

from ..git import (
    repository,
    primary_worktree,
)


# State and writer metadata are private to the repository owner.
PRIVATE_STATE_MODE: int = 0o700

HARNESS_ALIASES: dict[str, str] = {
    'cx': 'codex',
    'cld': 'claude',
    'oc': 'opencode',
    'claude-code': 'claude',
}


def canonical_harness(value: str) -> str:
    '''
    Normalize a CLI/legacy harness spelling for relation keys.

    - Record/choice/legacy-owner callers normalize through
      HARNESS_ALIASES before constructing `(harness, id)`.
    - Reject unsupported input with its original spelling.
    - `identity()` validates persisted canonical keys without
      rewriting them; aliases must not create a second stored dialog
      identity.

    '''
    original: str = value
    value = HARNESS_ALIASES.get(value, value)
    if value not in (
        'codex',
        'opencode',
        'claude',
    ):
        raise ValueError(f'Unsupported harness: {original!r}')
    return value


def encode(value: object) -> bytes:
    '''
    Encode deterministic UTF-8 JSON for previews and relation writes.

    - Sort keys and end with a newline so identical proposals have
      the same bytes, filename and human-reviewed SHA-256.
    - `save_wkt_preview()` and `update()` share this encoding.
    - Perform no I/O or schema validation.

    '''
    text: str = json.dumps(value, sort_keys=True, indent=2) + '\n'
    return text.encode()


def relation_dir(common: Path) -> Path:
    '''
    Locate shared .ai/state/dialogs without creating it.

    - Resolve the main checkout/bare root through
      git.primary_worktree().
    - All linked WKTs therefore read the same relations.json;
      deleting a linked WKT leaves its relation history available.
    - Reject symlinks in the selected state-directory components.
    - Read-only callers select this path without creating
      directories.

    '''
    root: Path = primary_worktree(common)
    directory: Path = root / '.ai/state/dialogs'
    location: Path
    for location in (
        root / '.ai',
        root / '.ai/state',
        directory,
    ):
        if location.is_symlink():
            location_text: str = str(location)
            raise ValueError(
                f'Relation directory is a symlink: '
                f'{location_text!r}',
            )
    return directory


def read(common: Path) -> tuple[dict, str]:
    '''
    Read validated relations.json records and their byte digest.

    - A missing file returns an empty schema-1 document and SHA-256
      of empty bytes; listing does not create repository state.
    - Reject symlinks, unsupported schemas, duplicate dialog
      identities and nonabsolute WKT/private Git-directory paths.
    - Let JSON/read failures propagate with their metadata context.
    - Check shape/identity here; `repository()` separately verifies
      current Git registration, so removed WKTs can remain
      historical.
    - WktIndexer embeds the digest as base_sha256; `update()` checks
      it under the writer guard before publishing changed relations.

    '''
    path: Path = relation_dir(common) / 'relations.json'
    path_text: str = str(path)
    if path.is_symlink():
        raise ValueError(
            f'Dialog relation file is a symlink: {path_text!r}'
        )
    try:
        raw: bytes = path.read_bytes()
    except FileNotFoundError:
        return {
            'schema': 1,
            'records': [],
        }, sha256(b'').hexdigest()
    data: dict = json.loads(raw)
    if (
        not isinstance(data, dict)
        or
        data.get('schema') != 1
        or
        not isinstance(data.get('records'), list)
    ):
        raise ValueError(
            f'Unsupported dialog relation file: {path_text!r}'
        )
    seen: set[tuple[str, str]] = set()
    record: dict
    for record in data['records']:
        if not isinstance(record, dict):
            raise ValueError(
                f'Invalid dialog relation in {path_text!r}: '
                f'{record!r}'
            )
        key: tuple[str, str] = identity(record)
        if key in seen:
            raise ValueError(
                f'Duplicate dialog relation in {path_text!r}: '
                f'{key!r}'
            )
        seen.add(key)
        field: str
        for field in (
            'worktree',
            'git_dir',
        ):
            value: object = record.get(field)
            if (
                not isinstance(value, str)
                or
                not Path(value).is_absolute()
            ):
                raise ValueError(
                    f'Invalid relation {field}: {value!r}; '
                    f'dialog={key!r}, file={path_text!r}'
                )
    return data, sha256(raw).hexdigest()


def list_wkt_relations(
    path: str = '.',
    harness: str|None = None,
    dialog_id: str|None = None,
) -> list[dict]:
    '''
    List saved dialog/WKT relations from any repo checkout.

    - `path` identifies the repo; optional harness/ID filters narrow
      its saved records. Harness aliases such as cx are accepted.
    - Join records to `list_dialogs()` by `(harness, id)`.
    - Return copies with git_active indicating a matching registered
      WKT and private Git directory. Removed WKTs retain their paths.
    - Read explicit relations only; do not infer legacy-owner/cwd
      pairs or scan harness logs. WktLookup owns those display
      fallbacks.
    - A missing file returns []; invalid repositories/metadata raise.

    '''
    selected: str|None = None
    if harness is not None:
        selected = canonical_harness(harness)
    common: Path
    inventory: dict[str, str]
    common, inventory = repository(path)
    data: dict
    digest: str
    data, digest = read(common)
    result: list[dict] = []
    item: dict
    for item in data['records']:
        if (
            selected is not None
            and
            item['harness'] != selected
        ):
            continue
        if (
            dialog_id is not None
            and
            item['id'] != dialog_id
        ):
            continue
        git_active: bool = (
            inventory.get(item['worktree']) == item['git_dir']
        )
        result.append({
            **item,
            'git_active': git_active,
        })
    return result


def identity(record: dict) -> tuple[str, str]:
    '''
    Validate and return a persisted `(harness, id)` relation key.

    - Preview grouping, relation validation and WktLookup use this to
      distinguish the same opaque ID under different harnesses.
    - Require canonical harness names and a nonempty string ID; IDs
      need not be UUIDs. Normalize CLI aliases separately.
    - Raise ValueError with the rejected field's value on invalid
      data.

    '''
    harness: object = record.get('harness')
    dialog_id: object = record.get('id')
    if harness not in (
        'codex',
        'opencode',
        'claude',
    ):
        raise ValueError(
            f'Invalid dialog harness {harness!r}; expected '
            f'codex, opencode or claude',
        )
    if not isinstance(dialog_id, str):
        kind: str = type(dialog_id).__name__
        raise ValueError(
            f'Invalid dialog id: expected str, got {kind}; '
            f'value={dialog_id!r}, harness={harness!r}',
        )
    if not dialog_id:
        raise ValueError('Invalid dialog id: empty string')
    return harness, dialog_id


def update(
    common: Path,
    additions: list[dict],
    expected: str|None = None,
    replace: bool = False,
) -> int:
    '''
    Publish reviewed dialog/WKT relations under an exclusive guard.

    Callers:
    - `apply_wkt_preview()` supplies an expected relation-file
      digest; history recovery cannot replace an existing relation.
    - `record_wkt_relation()` passes replace=True to retarget its one
      supplied dialog after checking Git registration.

    Publication:
    - Acquire write.guard with exclusive mkdir and write writer.json
      with this Python writer's PID. An existing guard raises intact.
    - Reread relations.json under that guard; reject a forbidden
      retarget or changed expected digest before publishing changed
      records.
    - Identical WKT/Git pairs return zero, even for a replayed
      preview. Empty additions still validate the expected digest.
    - Flush/fsync a temporary file, then replace relations.json.
      Return the number of changed relations.
    - Normal exits remove this writer's guard; crashes may require
      the operator recovery documented in docs/aiskillz.md.
    - Do not acquire, transfer or rewrite open-wkt lifecycle
      ownership.

    '''
    directory: Path = relation_dir(common)
    directory.mkdir(
        mode=PRIVATE_STATE_MODE,
        parents=True,
        exist_ok=True,
    )
    guard: Path = directory / 'write.guard'
    try:
        guard.mkdir(mode=PRIVATE_STATE_MODE)
    except FileExistsError:
        raise ValueError('Dialog index is locked: ' + str(guard))
    temporary: Path = guard / 'relations.json'
    owner: Path = guard / 'writer.json'
    try:
        owner.write_bytes(encode({'pid': os.getpid()}))
        data: dict
        digest: str
        data, digest = read(common)
        record: dict
        current: dict[tuple[str, str], dict] = {
            identity(record): record for record in data['records']
        }
        changed: int = 0
        for record in additions:
            key: tuple[str, str] = identity(record)
            previous: dict|None = current.get(key)
            if (
                previous is not None
                and
                previous['worktree'] == record['worktree']
                and
                previous['git_dir'] == record['git_dir']
            ):
                continue
            if (
                previous is not None
                and
                not replace
            ):
                raise ValueError(
                    f'Saved WKT relation would change: '
                    f'dialog={key!r}; '
                    f'old={previous!r}, proposed={record!r}'
                )
            current[key] = record
            changed += 1
        if not changed and additions:
            return 0
        if (
            expected is not None
            and
            digest != expected
        ):
            raise ValueError(
                f'WKT relations changed; preview again: '
                f'expected={expected!r}, actual={digest!r}'
            )
        if not changed:
            return 0
        data['records'] = list(current.values())
        stream: TextIO
        with temporary.open('x') as stream:
            stream.write(encode(data).decode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / 'relations.json')
        return changed
    finally:
        temporary.unlink(missing_ok=True)
        owner.unlink(missing_ok=True)
        guard.rmdir()
