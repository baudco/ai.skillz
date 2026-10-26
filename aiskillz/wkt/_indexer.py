# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Match dialog history to Git WKTs for an indexing preview.

- dialogs supplies metadata and a directory-history reader.
- WktIndexer owns repository scoping and evidence-based suggestions.
- aiskillz.git owns registration discovery; wkt._operations owns
  saving previews and writing relations after explicit review.

'''

from collections.abc import Callable
import json
from pathlib import Path

from ..git import (
    checkout_location,
    repository,
    primary_worktree,
)
from . import _relations as state


type HistoryReader = Callable[
    [
        list[dict],  # dialogs scoped to this repository
        list[str],  # warnings collected for the preview
    ],
    dict[
        tuple[str, str],  # (harness, dialog ID)
        set[str],  # directories observed in harness history
    ],
]


class WktIndexer:
    '''
    Propose dialog/WKT pairs for `ai.dlogs index` review.

    - `dialogs.preview_wkt_relations()` supplies metadata and an
      optional history reader; this class scopes its reads to one Git
      repository.
    - Match saved cwd, owner metadata and structured history to
      verified linked WKTs from `git.repository()`.
    - Return a proposal with evidence and unresolved dialog
      identities.
    - Leave harness parsing to dialogs._inspect and preview/relation
      writes to wkt._operations. Suggestion itself is read only.

    '''

    def __init__(self, path: str) -> None:
        '''
        Remember which checkout identifies the repository to inspect.

        - Defer discovery until `suggest()` so repeated calls see
          changed Git registrations and relation files.

        '''
        self.path: str = path

    def suggest(
        self,
        dialogs: list[dict],
        inspect_paths: HistoryReader|None = None,
        warnings: list[str]|None = None,
    ) -> dict:
        '''
        Suggest WKTs for dialogs without a saved relation.

        - Read verified Git WKTs and the current relations.json
          digest.
        - Prefer existing saved relations by leaving those dialogs
          alone.
        - Gather owner evidence, then inspect only repository-scoped
          dialogs.
        - One matching WKT is ready; several require a human
          --choose. No matching WKT leaves a scoped dialog in
          `unresolved`.
        - Return schema-1 entries, evidence, warnings, confirmed
          count and base_sha256 for `apply_wkt_preview()` to check
          later.
        - Copy the supplied warnings list; do not mutate a caller's
          list or write any preview, relation or ownership file.

        '''
        path: str = self.path
        # A preview owns its diagnostics; do not mutate a caller's
        # list.
        if warnings is None:
            warnings = []
        else:
            warnings = list(warnings)

        common: Path
        inventory: dict[str, str]
        common, inventory = repository(path)
        store: dict
        digest: str
        store, digest = state.read(common)
        record: dict
        confirmed: set[tuple[str, str]] = {
            state.identity(record) for record in store['records']
        }
        record: dict
        by_id: dict[tuple[str, str], dict] = {
            state.identity(record): record for record in dialogs
        }
        # Keep every evidence source per dialog/WKT. Selecting the
        # newest or first path here would hide a genuine ambiguity.
        candidates: dict[tuple[str, str], dict[str, set[str]]] = {}
        root: str
        private: str
        for root, private in inventory.items():
            try:
                owner: dict = json.loads((
                    Path(private) / 'ai-skillz-wkt/owner.json'
                ).read_text())
                dialog: dict|None = owner.get('dialog')
                source: str = 'verified-owner-dialog'
                if dialog is None:
                    dialog = {
                        'harness': state.canonical_harness(
                            owner.get('provider', ''),
                        ),
                        'id': owner.get('session'),
                    }
                    source = 'legacy-owner-matching-dialog-id'
                    if state.identity(dialog) not in by_id:
                        continue

                key: tuple[str, str] = state.identity(dialog)
                if key in confirmed:
                    continue
                candidates.setdefault(key, {}).setdefault(
                    root, set(),
                ).add(source)

            except (
                OSError,
                ValueError,
                TypeError,
                AttributeError,
            ):
                continue

        root: str
        repo_roots: list[Path] = [
            primary_worktree(common),
            *(Path(root) for root in inventory),
        ]
        scoped_paths: dict[str, bool] = {}

        def belongs(observed: str) -> bool:
            '''
            Check whether a recorded directory belongs to this repo.

            - Require containment under a main/linked checkout.
            - For existing paths, also compare the common Git
              directory; nested clones and submodules must not leak
              into this preview.
            - For removed paths, retain containment evidence because
              Git can no longer identify the directory's former
              repository.
            - Cache each decision in `scoped_paths` for this suggest
              call only.

            '''
            if observed not in scoped_paths:
                observed_path: Path = Path(observed)
                root: Path
                inside: bool = (
                    observed_path.is_absolute()
                    and any(
                        observed_path.resolve().is_relative_to(root)
                        for root in repo_roots
                    )
                )
                if inside and observed_path.exists():
                    location: tuple[str, ...] = checkout_location(
                        str(observed_path.resolve()),
                    )
                    inside = (
                        len(location) == 3
                        and Path(location[2]).resolve() == common
                    )

                scoped_paths[observed] = inside

            return scoped_paths[observed]

        record: dict
        scoped: list[dict] = [
            record for record in dialogs
            if (
                state.identity(record) in candidates
                or belongs(record.get('cwd', ''))
            )
        ]
        history: dict[tuple[str, str], set[str]] = {}
        if inspect_paths:
            history = inspect_paths(scoped, warnings)
        unresolved: list[dict] = []
        # Prefer the most specific registered root when WKTs nest.
        roots: list[str] = sorted(inventory, key=len, reverse=True)
        record: dict
        for record in scoped:
            key = state.identity(record)
            if key in confirmed:
                continue
            cwd: str = record.get('cwd', '')
            observed: str
            for observed in {
                cwd,
                *history.get(key, set()),
            }:
                if not belongs(observed):
                    continue
                observed_path: Path = Path(observed).resolve()
                root: str
                for root in roots:
                    if observed_path.is_relative_to(root):
                        source = 'structured-cwd-or-tool-workdir'
                        if observed == cwd:
                            source = 'saved-cwd'
                        candidates.setdefault(key, {}).setdefault(
                            root, set(),
                        ).add(source)
                        break

            p: Path
            if (
                key not in candidates
                and Path(cwd).is_absolute()
                and
                any(Path(cwd).is_relative_to(p) for p in repo_roots)
            ):
                unresolved.append({
                    'harness': key[0],
                    'id': key[1],
                    'name': record['name'],
                })

        entries: list[dict] = []
        key: tuple[str, str]
        choices: dict[str, set[str]]
        for key, choices in sorted(candidates.items()):
            status: str = 'ambiguous'
            if len(choices) == 1:
                status = 'ready'

            entries.append({
                'harness': key[0],
                'id': key[1],
                'name': by_id.get(key, {}).get('name', '(metadata)'),
                'status': status,
                'candidates': [
                    {
                        'worktree': root,
                        'git_dir': inventory[root],
                        'evidence': sorted(choices[root]),
                    }
                    for root in sorted(choices)
                ],
            })

        return {
            'schema': 1,
            'kind': 'dialog-wkt-preview',
            'common_dir': str(common),
            'base_sha256': digest,
            'entries': entries,
            'unresolved': unresolved,
            'confirmed': len(confirmed),
            'warnings': warnings,
        }
