# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Resolve worktree paths for dialog listing without changing metadata.

`cli.format_dialog_table()` uses one WktLookup per invocation.
It prefers relations.json, falls back to old owner.json dialog
fields, then to Git discovery at the saved dialog cwd. Python callers
can use roots() to obtain absolute paths instead of display labels.

'''

import json
from pathlib import Path

from ..git import checkout_location, repository


class WktLookup:
    '''
    Read worktree paths associated with dialogs, caching one listing.

    cli.format_dialog_table() creates one instance and calls roots()
    for each row. locations remembers Git paths for each saved cwd,
    while relations remembers dialog/worktree pairs for each
    repository. Discard the instance after listing to see subsequent
    file changes.

    Relations written by open-wkt or index --apply take precedence
    over old owner.json dialog fields. Multiple old relations
    remain a set of paths; the CLI decides how to display them.

    '''

    def __init__(self) -> None:
        '''
        Create empty caches for a single dialog listing.

        roots() populates these dictionaries on demand. Construction
        has no filesystem side effects.

        '''
        self.locations: dict[str, tuple[str, ...]] = {}
        self.relations: dict[
            str, dict[tuple[str, str], set[str]]
        ] = {}

    def roots(
        self,
        cwd: str,
        harness: str = '',
        dialog_id: str = '',
    ) -> set[str]:
        '''
        Return absolute worktree paths for the supplied dialog.

        Resolve the Git repository containing its saved cwd, then
        read the relation file once per repository. If no existing
        associated worktree is found, use the linked checkout
        containing that cwd. The main checkout and missing/deleted
        cwd paths return an empty set. These paths describe recorded
        worktree use, not a running agent cwd.

        '''
        if cwd not in self.locations:
            self.locations[cwd] = checkout_location(cwd)
        paths: tuple[str, ...] = self.locations[cwd]
        if len(paths) != 3:
            return set()
        common: str = paths[2]
        if (
            harness
            and
            dialog_id
        ):
            if common not in self.relations:
                self.relations[common] = self._read(cwd, common)
            names: set[str] = self.relations[common].get(
                (harness, dialog_id), set(),
            )
            if names:
                return set(names)
        if paths[1] == common:
            return set()
        return {paths[0]}

    def _read(
        self,
        cwd: str,
        common: str,
    ) -> dict[tuple[str, str], set[str]]:
        '''
        Read relation JSON and old owner files for one repository.

        roots() calls this once per common Git directory. Verify each
        path against git.repository(). A written relation
        suppresses older owner.json evidence for the same dialog,
        even if the worktree was removed. Preserve several old
        worktree paths as a set.

        Ignore malformed old owner fields; fail visibly for a
        malformed relations.json file. Generic ownership tokens
        are not dialog IDs; WktIndexer can match them against
        known harness IDs when recovering old relations. This
        method never rewrites owner files.

        '''
        from ._relations import read, identity

        resolved: Path
        inventory: dict[str, str]
        resolved, inventory = repository(cwd)
        if str(resolved) != common:
            return {}
        store: dict
        digest: str
        store, digest = read(resolved)
        result: dict[tuple[str, str], set[str]] = {}
        confirmed: set[tuple[str, str]] = set()
        record: dict
        for record in store['records']:
            key: tuple[str, str] = identity(record)
            confirmed.add(key)
            root: str = record['worktree']
            if inventory.get(root) == record['git_dir']:
                result[key] = {root}
        root: str
        private: str
        for root, private in inventory.items():
            try:
                owner: dict = json.loads((
                    Path(private) / 'ai-skillz-wkt/owner.json'
                ).read_text())
                dialog: dict = owner.get('dialog', {})
                key = identity(dialog)
                if key not in confirmed:
                    result.setdefault(key, set()).add(root)
            except (
                OSError,
                ValueError,
                AttributeError,
                TypeError,
            ):
                continue
        return result
