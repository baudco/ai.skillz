# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Read and write the repository's dialog-to-worktree relations.

A relation records that a dialog uses a particular worktree.
`owner.json` separately identifies the agent allowed to manage and
remove that worktree under `/open-wkt` rules. These are independent:
several dialogs can have used one worktree under different owners.

`wkt._operations.record_wkt_relation()` writes a known pair.
`apply_wkt_preview()` writes pairs reviewed through ai.dlogs
index. Both use `update()` and the same relations.json file.
`read()` and `list_wkt_relations()` supply Python callers and
CLI lookup.

`write.guard` is an exclusive mkdir lock. writer.json holds the
Python writer PID; update() checks the file digest under that lock,
then atomically replaces relations.json. See docs/aiskillz.md for
crash recovery and the deferred KDL format migration.

'''

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import TextIO

from ..git import repository, primary_worktree


HARNESS_ALIASES: dict[str, str] = {
    'cx': 'codex',
    'cld': 'claude',
    'oc': 'opencode',
    'claude-code': 'claude',
}


def canonical_harness(value: str) -> str:
    '''
    Normalize a CLI or legacy owner spelling to a stored harness key.

    `record_wkt_relation()`, explicit preview choices and
    legacy-owner import call this before constructing
    `(harness, id)` identities.
    Resolve `HARNESS_ALIASES` here so `cx` and `codex` cannot create
    separate relations. Unsupported spellings raise `ValueError`;
    `identity()` validates already-canonical persisted records
    without normalizing.

    '''
    value = HARNESS_ALIASES.get(value, value)
    if value not in ('codex', 'opencode', 'claude'):
        raise ValueError('Unsupported harness: ' + value)
    return value


def encode(value: object) -> bytes:
    '''
    Produce deterministic UTF-8 JSON bytes for local metadata.

    `save_wkt_preview()` hashes these exact bytes for the
    filename and the human's apply pin. `update()` uses the same
    encoding for relation and writer files. Sorted keys and a
    trailing newline keep identical proposals byte-identical; this
    helper performs no I/O and does not validate the supplied
    object's schema.

    '''
    text: str = json.dumps(value, sort_keys=True, indent=2) + '\n'
    return text.encode()


def relation_dir(common: Path) -> Path:
    '''
    Locate the shared .ai/state/dialogs directory for this
    repository.

    Every checkout resolves to the main checkout (or bare repo root)
    through `git.primary_worktree()`. Removing a linked worktree
    therefore leaves the shared relation files available.
    This selects a path; read-only callers never create directories.

    '''
    root: Path = primary_worktree(common)
    directory: Path = root / '.ai/state/dialogs'
    location: Path
    for location in (
        root / '.ai', root / '.ai/state', directory,
    ):
        if location.is_symlink():
            raise ValueError(
                'Relation directory is a symlink: '
                + str(location),
            )
    return directory


def read(common: Path) -> tuple[dict, str]:
    '''
    Load validated `relations.json` records and their byte digest.

    `WktIndexer.suggest()` embeds this digest as `base_sha256`;
    `update()` compares it at apply time. `WktLookup._read()`
    consumes the same records to render confirmed relations. A
    missing file returns an empty schema-1 document and SHA-256 of
    empty bytes, without creating state during ordinary dialog
    display.

    Reject unknown schemas, duplicate identities and nonabsolute root
    or Git-directory fields. JSON/read errors propagate to the
    caller. Path existence and Git registration are checked
    separately through `repository()`, so records for removed trees
    can remain historical.

    '''
    path: Path = relation_dir(common) / 'relations.json'
    if path.is_symlink():
        raise ValueError('Dialog relation file is a symlink')
    try:
        raw: bytes = path.read_bytes()
    except FileNotFoundError:
        return {'schema': 1, 'records': []}, sha256(b'').hexdigest()
    data: dict = json.loads(raw)
    if (
        not isinstance(data, dict)
        or
        data.get('schema') != 1
        or
        not isinstance(data.get('records'), list)
    ):
        raise ValueError('Unsupported dialog relation file')
    seen: set[tuple[str, str]] = set()
    record: dict
    for record in data['records']:
        if not isinstance(record, dict):
            raise ValueError('Invalid dialog relation')
        key: tuple[str, str] = identity(record)
        if key in seen:
            raise ValueError('Duplicate dialog relation')
        seen.add(key)
        field: str
        for field in ('worktree', 'git_dir'):
            value: object = record.get(field)
            if (
                not isinstance(value, str)
                or
                not Path(value).is_absolute()
            ):
                raise ValueError('Invalid relation ' + field)
    return data, sha256(raw).hexdigest()


def list_wkt_relations(
    path: str = '.',
    harness: str|None = None,
    dialog_id: str|None = None,
) -> list[dict]:
    '''
    Read saved dialog/WKT relations from any repository checkout.

    Workspace callers can join these records to `list_dialogs()` by
    `(harness, id)` without invoking the CLI. `path` selects a repo
    through any existing checkout; optional filters narrow its
    records. Harness aliases such as `cx` are accepted. This reads
    the same file as `WktLookup`, without inferring relations
    from legacy owners or saved cwd.

    Return copies of stored records with a `git_active` boolean
    indicating whether the registered WKT and private Git directory
    match. Removed targets remain available for historical tooling;
    the table displays only Git-active WKTs. Missing files return an
    empty list; invalid repos or metadata raise instead of claiming
    there are no relations. No harness logs are scanned or written.

    '''
    selected: str|None = (
        canonical_harness(harness) if harness is not None else None
    )
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
        result.append({**item, 'git_active': git_active})
    return result


def identity(record: dict) -> tuple[str, str]:
    '''
    Validate a relation's persisted `(harness, id)` identity.

    Relation-file validation, preview grouping and display lookup
    use this to distinguish identical IDs in different harnesses.
    Harness names must already be canonical; CLI aliases go through
    `canonical_harness()` first. IDs must be nonempty strings, not
    necessarily UUIDs. Raise `ValueError` for invalid metadata.

    '''
    harness: object = record.get('harness')
    dialog_id: object = record.get('id')
    if harness not in ('codex', 'opencode', 'claude'):
        raise ValueError(
            f'Invalid dialog harness {harness!r}; expected '
            f'codex, opencode or claude',
        )
    if not isinstance(dialog_id, str):
        kind: str = type(dialog_id).__name__
        raise ValueError(
            f'Invalid dialog id: expected str, got {kind}',
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
    Publish WKT relations under an exclusive writer guard.

    `apply_wkt_preview()` supplies its saved `expected` digest
    and leaves `replace=False`: history recovery cannot overwrite
    saved relations. `record_wkt_relation()` uses `replace=True`
    to retarget only the supplied dialog after caller verification.
    Callers validate WKTs through `repository()` first.

    Create `write.guard`, write its `writer.json` PID, then reread
    `relations.json` while holding it. Identical WKT/Git-directory
    pairs are no-ops and return zero even when an old preview is
    replayed. Otherwise reject a changed expected digest or a
    forbidden retarget. Write and fsync a temporary file before
    replacing `relations.json`. Return the number of changed
    relations.

    Normal exits remove this writer's guard; an existing guard raises
    `ValueError` and is left intact. A crash can leave a guard
    requiring operator inspection as described in `docs/aiskillz.md`.
    This helper never acquires, transfers or rewrites worktree
    lifecycle ownership.

    '''
    directory: Path = relation_dir(common)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    guard: Path = directory / 'write.guard'
    try:
        guard.mkdir(mode=0o700)
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
                raise ValueError('Saved WKT relation would change')
            current[key] = record
            changed += 1
        if not changed:
            return 0
        if (
            expected is not None
            and
            digest != expected
        ):
            raise ValueError('WKT relations changed; preview again')
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
