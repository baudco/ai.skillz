# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Resolve recorded WKT paths for dialog listing and resume.

- cli.format_dialog_table() creates one WktLookup per invocation.
- Prefer relations.json, then owner.json dialog fields, then the Git
  checkout containing saved cwd. Retain inactive paths for diagnosis.
- Library callers use roots() for verified absolute paths and
  recorded_roots() for explicit paths that may be unavailable.

'''

import json
from pathlib import Path

from ..git import (
    checkout_location,
    repository,
)


class WktLookup:
    '''
    Resolve dialog WKTs during one listing or resume selection.

    - `cli.format_dialog_table()` creates one instance per listing.
    - Cache Git results by saved cwd in `WktLookup.locations`, and
      relation results by common Git directory in
      WktLookup.relations.
    - Prefer relations.json over old owner.json dialog fields, then
      fall back to the linked checkout containing the saved cwd.
    - Keep recorded paths separately in WktLookup.recorded_relations
      so removed WKTs remain visible without becoming launch targets.
    - Discard the instance to observe later file/Git changes.

    '''

    def __init__(self) -> None:
        '''
        Initialize the per-invocation Git and relation caches.

        - `roots()` populates WktLookup.locations and
          WktLookup.relations.
        - `_read()` also fills WktLookup.recorded_relations for
          diagnostics.
        - Construction performs no reads or writes.

        '''
        self.locations: dict[str, tuple[str, ...]] = {}
        self.relations: dict[
            str, dict[tuple[str, str], set[str]]
        ] = {}
        self.recorded_relations: dict[
            str, dict[tuple[str, str], set[str]]
        ] = {}

    def recorded_roots(
        self,
        cwd: str,
        harness: str,
        dialog_id: str,
    ) -> set[str]:
        '''
        Return saved relation paths, including unavailable WKTs.

        - Populate this repository's caches through `roots()` first.
        - Return a copy from WktLookup.recorded_relations, or an
          empty set when saved cwd cannot identify the Git
          repository.
        - Listing/resume use these paths to explain unavailable
          relations; use `roots()` for verified launch-directory
          candidates.

        '''
        self.roots(cwd, harness, dialog_id)
        paths: tuple[str, ...] = self.locations.get(cwd, ())
        if len(paths) != 3:
            return set()
        records: dict[tuple[str, str], set[str]] = (
            self.recorded_relations.get(paths[2], {})
        )
        return set(records.get((
            harness,
            dialog_id,
        ), set()))

    def roots(
        self,
        cwd: str,
        harness: str = '',
        dialog_id: str = '',
    ) -> set[str]:
        '''
        Find verified WKTs for a dialog's saved directory.

        - Cache the Git location by cwd and read each repository
          once.
        - Prefer a recorded `(harness, dialog_id)` relation,
          including an empty set when its WKT is no longer
          registered.
        - With no relation, return the linked checkout containing
          saved cwd.
        - Return an empty set for the main checkout or an unusable
          cwd.
        - These paths describe recorded use, not a running agent's
          cwd.

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
            key: tuple[str, str] = (
                harness,
                dialog_id,
            )
            if key in self.relations[common]:
                return set(self.relations[common][key])

        if paths[1] == common:
            return set()
        return {paths[0]}

    def has_relation(
        self,
        cwd: str,
        harness: str,
        dialog_id: str,
    ) -> bool:
        '''
        Check whether a dialog has an explicit recorded relation.

        - Populate WktLookup.relations through `roots()` first.
        - An entry with an empty WKT set still counts: it preserves
          the recorded dialog identity after removal of the worktree.
        - `resume_target()` uses this to warn before falling back to
          saved cwd. Missing Git-location information returns False.

        '''
        self.roots(cwd, harness, dialog_id)
        paths: tuple[str, ...] = self.locations.get(cwd, ())
        if len(paths) != 3:
            return False
        return (
            harness,
            dialog_id,
        ) in self.relations[paths[2]]

    def _read(
        self,
        cwd: str,
        common: str,
    ) -> dict[tuple[str, str], set[str]]:
        '''
        Combine saved relations and owner evidence for one repo.

        - `roots()` calls this once per common Git directory.
        - Verify paths through `git.repository()`; preserve recorded
          paths separately from paths whose WKT/private Git directory
          still match.
        - An explicit relation suppresses older owner evidence for
          that dialog even when its recorded WKT was removed.
        - Preserve several legacy owner matches as a set; do not
          choose one.
        - Ignore malformed legacy owner fields; malformed
          relations.json raises. WktIndexer separately matches
          generic legacy owner tokens against known dialog IDs. Never
          rewrite owner files.

        '''
        from ._relations import (
            read,
            identity,
        )

        resolved: Path
        inventory: dict[str, str]
        resolved, inventory = repository(cwd)
        if str(resolved) != common:
            return {}
        store: dict
        digest: str
        store, digest = read(resolved)
        result: dict[tuple[str, str], set[str]] = {}
        self.recorded_relations[common] = {}
        confirmed: set[tuple[str, str]] = set()
        record: dict
        for record in store['records']:
            key: tuple[str, str] = identity(record)
            confirmed.add(key)
            # Keep an explicit empty result when a recorded WKT is
            # gone. Otherwise roots() would fall through to saved cwd
            # and accidentally present that as the recorded relation.
            result[key] = set()
            root: str = record['worktree']
            self.recorded_relations[common][key] = {root}
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
