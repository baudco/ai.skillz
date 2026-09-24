# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Save suggested dialog/WKT pairs and write reviewed relations.

The dialog API calls these operations for ai.dlogs index and
open-wkt. A preview file contains proposed dialog/worktree pairs and
a digest of relations.json as it was read. Applying it verifies
the exact file and current Git registrations before updating
relations.json.

'''

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from ..git import repository
from . import _relations as state


def save_wkt_preview(data: dict) -> tuple[Path, str]:
    '''
    Publish a deterministic proposal and return its path and digest.

    `cli.index_main()` calls this after building a proposal. Hash
    its exact bytes and publish `<digest>.json` in the shared
    relation directory's previews subdirectory. The CLI prints
    these values for the human's later `--apply`/`--sha256`
    invocation.

    Use a flushed temporary file and exclusive hard-link publication;
    an existing identical proposal is reused, while a different file
    or symlink at the destination is refused. No saved relation
    is written, including for empty proposals. Only local preview
    artifacts and their containing directories are created.

    '''
    raw: bytes = state.encode(data)
    digest: str = sha256(raw).hexdigest()
    directory: Path = state.relation_dir(Path(data['common_dir']))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = directory / 'previews'
    if directory.is_symlink():
        raise ValueError('Preview directory is a symlink')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path: Path = directory / (digest + '.json')
    stream: tempfile._TemporaryFileWrapper
    with tempfile.NamedTemporaryFile(
        dir=directory, delete=False,
    ) as stream:
        temporary: Path = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if (
                    path.is_symlink()
                    or
                    path.read_bytes() != raw
                ):
                    raise ValueError('Existing preview differs')
        finally:
            temporary.unlink(missing_ok=True)
    return path, digest


def apply_wkt_preview(
    repo: str,
    path: Path,
    digest: str,
    choose: list[str],
) -> int:
    '''
    Save WKT relations selected from a human-reviewed preview.

    `main()` enters here only for `--apply` with an explicit digest.
    Authenticate `path` bytes, schema and common repository identity;
    revalidate each selected root and private Git directory against
    `git.repository()` before calling its `update()` writer.

    Single-candidate entries are selected automatically. Ambiguous
    entries stay unassigned unless `choose` contains a matching
    `harness:ID=/path` selection; aliases are accepted. Reject
    duplicate, unknown or out-of-proposal choices rather than
    guessing.

    `update()` checks the preview's `base_sha256` under its guard
    and refuses a changed relation file or replacement of saved
    relations. Repeating identical relations returns zero. Return
    the number of relations written; ownership and the preview file
    stay untouched. Invalid artifacts or stale targets raise errors
    for CLI reporting.

    '''
    raw: bytes = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Preview SHA-256 mismatch')
    data: dict = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Invalid preview object')
    common: Path
    inventory: dict[str, str]
    common, inventory = repository(repo)
    if (
        data.get('schema') != 1
        or
        data.get('kind') != 'dialog-wkt-preview'
        or
        data.get('common_dir') != str(common)
    ):
        raise ValueError('Preview schema/repository mismatch')
    selections: dict[tuple[str, str], str] = {}
    selection: str
    for selection in choose:
        identity: str
        target: str
        identity, target = selection.split('=', 1)
        harness: str
        dialog_id: str
        harness, dialog_id = identity.split(':', 1)
        key: tuple[str, str] = (
            state.canonical_harness(harness), dialog_id,
        )
        if key in selections:
            raise ValueError('Duplicate dialog choice')
        selections[key] = str(Path(target).expanduser().resolve())
    additions: list[dict] = []
    entry: dict
    for entry in data['entries']:
        key = state.identity(entry)
        choices: list[dict] = entry['candidates']
        target: str|None = selections.pop(key, None)
        if (
            target is None
            and
            len(choices) != 1
        ):
            continue
        candidate: dict
        matches: list[dict] = [
            candidate for candidate in choices
            if target in (None, candidate['worktree'])
        ]
        if len(matches) != 1:
            raise ValueError('Choice is not a preview candidate')
        candidate = matches[0]
        root: str = candidate['worktree']
        if inventory.get(root) != candidate['git_dir']:
            raise ValueError('Worktree changed; preview again')
        additions.append({
            'harness': key[0], 'id': key[1], **candidate,
            'source': 'index-preview', 'preview_sha256': digest,
        })
    if selections:
        raise ValueError('Choice refers to a dialog outside preview')
    return state.update(common, additions, data['base_sha256'])


def record_wkt_relation(
    repo: str,
    harness: str,
    dialog_id: str,
    wkt: str,
) -> int:
    '''
    Record a dialog/WKT relation supplied by a skill or human.

    `/open-wkt` verifies the WKT's lifecycle owner, resolves the
    current harness dialog ID and invokes the source CLI's
    `--record HARNESS ID` mode. A human may also supply both values
    explicitly. This function checks Git registration but cannot
    independently prove that `dialog_id` belongs to the caller's
    running harness instance.

    Resolve `repo` and `wkt`, require a registered live linked tree,
    normalize the harness and call
    `_relations.update(replace=True)`. Retarget only this
    dialog's relation; retain other dialogs and leave
    `owner.json` unchanged. Return zero for an identical existing
    relation or one for a new/changed relation. Invalid WKTs
    or active writer guards fail visibly without recreating the
    worktree.

    '''
    common: Path
    inventory: dict[str, str]
    common, inventory = repository(repo)
    root: str = str(Path(wkt).expanduser().resolve())
    if root not in inventory:
        raise ValueError('Target is not a live linked worktree')
    addition: dict = {
        'harness': state.canonical_harness(harness), 'id': dialog_id,
        'worktree': root, 'git_dir': inventory[root],
        'source': 'explicit-record',
    }
    state.identity(addition)
    return state.update(common, [addition], replace=True)
