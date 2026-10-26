# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Save WKT proposals and publish explicitly reviewed relations.

- ai.dlogs index saves proposed pairs plus the relations.json digest
  observed during discovery; it prints the preview's own SHA-256.
- apply_wkt_preview() verifies those bytes and current Git paths
  before asking _relations.update() to publish selected pairs.
- record_wkt_relation() writes one explicit pair for /open-wkt or a
  human caller. Neither operation transfers lifecycle ownership.

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
    Save a proposal file and return its path and SHA-256.

    - `cli.index_main()` calls this with preview_wkt_relations()
      output.
    - Hash exact deterministic bytes; publish previews/<digest>.json
      in the repository's shared relation directory.
    - Flush a temporary file, then use an exclusive hard link so
      another writer cannot replace the human-reviewed destination.
    - Reuse an identical existing preview; reject different bytes or
      a symlink at that path.
    - Create preview artifacts only, including for empty proposals;
      this does not record any dialog/WKT relation.

    '''
    raw: bytes = state.encode(data)
    digest: str = sha256(raw).hexdigest()
    directory: Path = state.relation_dir(Path(data['common_dir']))
    directory.mkdir(
        mode=state.PRIVATE_STATE_MODE,
        parents=True,
        exist_ok=True,
    )
    directory = directory / 'previews'
    if directory.is_symlink():
        directory_text: str = str(directory)
        raise ValueError(
            f'Preview directory is a symlink: {directory_text!r}'
        )
    directory.mkdir(
        mode=state.PRIVATE_STATE_MODE,
        parents=True,
        exist_ok=True,
    )
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
                    path_text: str = str(path)
                    raise ValueError(
                        f'Existing preview differs: {path_text!r}'
                    )
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
    Record pairs from a human-reviewed, digest-pinned preview.

    Validation:
    - `cli.index_main()` requires --apply and --sha256 before
      calling.
    - Check exact bytes, schema and common Git repository identity.
    - Recheck each selected WKT/private Git directory against the
      current git.repository() inventory before any relation write.

    Selection:
    - Take single-candidate entries automatically.
    - Leave ambiguous entries alone unless `choose` supplies an exact
      harness:ID=/path choice. Harness aliases are accepted.
    - Reject duplicate, unknown or out-of-proposal selections.

    Publication:
    - `_relations.update()` checks base_sha256 under its writer guard
      and refuses replacement of existing relations.
    - Identical replay returns zero; otherwise return the write
      count.
    - Leave the preview file and lifecycle owner metadata unchanged.
      Invalid or stale inputs raise for CLI reporting.

    '''
    path_text: str = str(path)
    raw: bytes = path.read_bytes()
    actual_digest: str = sha256(raw).hexdigest()
    if actual_digest != digest:
        raise ValueError(
            f'Preview SHA-256 mismatch: file={path_text!r}; '
            f'expected={digest!r}, actual={actual_digest!r}'
        )
    data: dict = json.loads(raw)
    if not isinstance(data, dict):
        data_type: str = type(data).__name__
        raise ValueError(
            f'Invalid preview object: file={path_text!r}, '
            f'type={data_type!r}'
        )
    common: Path
    inventory: dict[str, str]
    common, inventory = repository(repo)
    schema: object = data.get('schema')
    kind: object = data.get('kind')
    recorded_common: object = data.get('common_dir')
    common_text: str = str(common)
    if (
        data.get('schema') != 1
        or
        data.get('kind') != 'dialog-wkt-preview'
        or
        data.get('common_dir') != str(common)
    ):
        raise ValueError(
            f'Preview schema/repository mismatch: '
            f'file={path_text!r}; '
            f'schema={schema!r}, '
            f'kind={kind!r}, '
            f'common_dir={recorded_common!r}, '
            f'expected_common={common_text!r}'
        )
    entries: object = data.get('entries')
    if not isinstance(entries, list):
        raise ValueError(
            f'Invalid preview entries: expected list, '
            f'got {entries!r}; '
            f'file={path_text!r}'
        )
    expected: object = data.get('base_sha256')
    if not isinstance(expected, str):
        raise ValueError(
            f'Invalid preview base_sha256: expected str, '
            f'got {expected!r}; file={path_text!r}'
        )
    selections: dict[tuple[str, str], str] = {}
    selection: str
    for selection in choose:
        identity: str
        target: str
        try:
            identity, target = selection.split('=', 1)
        except ValueError as error:
            raise ValueError(
                f'Invalid dialog choice {selection!r}; '
                f'expected HARNESS:ID=/absolute/worktree'
            ) from error
        harness: str
        dialog_id: str
        try:
            harness, dialog_id = identity.split(':', 1)
        except ValueError as error:
            raise ValueError(
                f'Invalid dialog choice {selection!r}; '
                f'expected HARNESS:ID=/absolute/worktree'
            ) from error
        key: tuple[str, str] = (
            state.canonical_harness(harness),
            dialog_id,
        )
        if key in selections:
            raise ValueError(
                f'Duplicate dialog choice: {selection!r}'
            )
        selections[key] = str(Path(target).expanduser().resolve())
    additions: list[dict] = []
    entry: object
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(
                f'Invalid preview entry: expected object, '
                f'got {entry!r}',
            )
        key = state.identity(entry)
        choices: object = entry.get('candidates')
        if not isinstance(choices, list):
            raise ValueError(
                f'Invalid preview candidates: expected list, '
                f'got {choices!r}; dialog={key!r}',
            )
        candidate: object
        for candidate in choices:
            if not isinstance(candidate, dict):
                raise ValueError(
                    f'Invalid preview candidate: expected object, '
                    f'got {candidate!r}; dialog={key!r}'
                )
            if (
                not isinstance(candidate.get('worktree'), str)
                or not isinstance(candidate.get('git_dir'), str)
            ):
                raise ValueError(
                    f'Invalid preview candidate paths: '
                    f'{candidate!r}; dialog={key!r}'
                )
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
            if target in (
                None,
                candidate['worktree'],
            )
        ]
        if len(matches) != 1:
            raise ValueError(
                f'Choice is not a preview candidate: '
                f'dialog={key!r}, target={target!r}'
            )
        candidate = matches[0]
        root: str = candidate['worktree']
        current_git: str|None = inventory.get(root)
        recorded_git: str = candidate['git_dir']
        if current_git != recorded_git:
            raise ValueError(
                f'Worktree changed; preview again: {root!r}; '
                f'recorded_git={recorded_git!r}, '
                f'current_git={current_git!r}'
            )
        additions.append({
            'harness': key[0],
            'id': key[1],
            'worktree': candidate['worktree'],
            'git_dir': candidate['git_dir'],
            'source': 'index-preview',
            'preview_sha256': digest,
        })
    if selections:
        raise ValueError(
            f'Choice refers to a dialog outside preview: '
            f'{selections!r}'
        )
    return state.update(common, additions, expected)


def record_wkt_relation(
    repo: str,
    harness: str,
    dialog_id: str,
    wkt: str,
) -> int:
    '''
    Record one explicitly supplied dialog/WKT pair.

    - `/open-wkt` verifies lifecycle ownership and finds the current
      harness dialog ID before calling through --record HARNESS ID. A
      human can also supply the pair directly.
    - Resolve repo/WKT, require a verified linked checkout and
      normalize the harness. This function cannot prove the caller
      owns the ID.
    - `_relations.update(replace=True)` retargets only this dialog;
      other relations and owner.json remain unchanged.
    - Return zero for an identical relation, one for a new/changed
      pair.
    - Invalid WKTs or writer guards raise; never recreate a missing
      WKT.

    '''
    common: Path
    inventory: dict[str, str]
    common, inventory = repository(repo)
    root: str = str(Path(wkt).expanduser().resolve())
    if root not in inventory:
        raise ValueError(
            f'Target is not a live linked worktree: {root!r}; '
            f'repo={repo!r}, harness={harness!r}, id={dialog_id!r}'
        )
    addition: dict = {
        'harness': state.canonical_harness(harness),
        'id': dialog_id,
        'worktree': root,
        'git_dir': inventory[root],
        'source': 'explicit-record',
    }
    state.identity(addition)
    return state.update(common, [addition], replace=True)
