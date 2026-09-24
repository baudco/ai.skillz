# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Match dialog history to registered Git worktrees for user review.

`dialogs` supplies harness metadata and directory observations. This
module owns repository scoping and relation decisions; `git` owns
worktree discovery, and `_operations` owns saving and applying
results.

'''

from collections.abc import Callable
import json
from pathlib import Path

from ..git import repository, primary_worktree
from . import _relations as state


HistoryReader = Callable[
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
    Propose dialog/worktree pairs from Git and supplied dialog
    history.

    `dialogs.preview_wkt_relations()` supplies metadata and a
    history reader. This class scopes those reads to the repository,
    matches recorded directories to live Git worktrees and returns a
    reviewable proposal. It neither parses harness files itself nor
    writes relations; `_operations` handles preview files and
    publication after the user invokes --apply or --record.

    '''

    def __init__(self, path: str) -> None:
        '''
        Remember the checkout used to identify this Git repository.

        Discovery happens when `suggest()` is called, so repeated
        calls see changed WKT registrations and relation files.

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

        One matching WKT is ready for user review; several require a
        `--choose` selection. Return schema-1 preview data with each
        matching WKT and its evidence, unresolved dialog IDs and the
        relation-file digest checked during `--apply`. Supplied
        history-reader failures append to `warnings`.

        '''
        path: str = self.path
        warnings = [] if warnings is None else list(warnings)
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
        by_id: dict[tuple[str, str], dict] = {
            state.identity(record): record for record in dialogs
        }
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
        repo_roots: list[Path] = [
            primary_worktree(common),
            *(Path(root) for root in inventory),
        ]
        root_path: Path
        scoped: list[dict] = [
            record for record in dialogs
            if (
                state.identity(record) in candidates
                or
                any(
                    Path(record.get('cwd', '')).is_relative_to(
                        root_path,
                    )
                    for root_path in repo_roots
                )
            )
        ]
        history: dict[tuple[str, str], set[str]] = (
            inspect_paths(scoped, warnings) if inspect_paths else {}
        )
        unresolved: list[dict] = []
        roots: list[str] = sorted(inventory, key=len, reverse=True)
        p: Path
        for record in scoped:
            key = state.identity(record)
            if key in confirmed:
                continue
            cwd: str = record.get('cwd', '')
            observed: str
            for observed in {cwd, *history.get(key, set())}:
                if not Path(observed).is_absolute():
                    continue
                observed_path: Path = Path(observed).resolve()
                for root in roots:
                    if observed_path.is_relative_to(root):
                        source = (
                            'saved-cwd' if observed == cwd
                            else 'structured-cwd-or-tool-workdir'
                        )
                        candidates.setdefault(key, {}).setdefault(
                            root, set(),
                        ).add(source)
                        break
            if (
                key not in candidates
                and
                Path(cwd).is_absolute()
                and
                any(Path(cwd).is_relative_to(p) for p in repo_roots)
            ):
                unresolved.append({
                    'harness': key[0], 'id': key[1],
                    'name': record['name'],
                })
        entries: list[dict] = []
        key: tuple[str, str]
        choices: dict[str, set[str]]
        for key, choices in sorted(candidates.items()):
            entries.append({
                'harness': key[0], 'id': key[1],
                'name': by_id.get(key, {}).get('name', '(metadata)'),
                'status': (
                    'ready' if len(choices) == 1 else 'ambiguous'
                ),
                'candidates': [
                    {
                        'worktree': root, 'git_dir': inventory[root],
                        'evidence': sorted(choices[root]),
                    }
                    for root in sorted(choices)
                ],
            })
        return {
            'schema': 1, 'kind': 'dialog-wkt-preview',
            'common_dir': str(common), 'base_sha256': digest,
            'entries': entries, 'unresolved': unresolved,
            'confirmed': len(confirmed), 'warnings': warnings,
        }
