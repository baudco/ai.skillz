# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Inspect Git repository paths and verified WKT registrations.

- Own common/private Git paths, registration and backlink checks.
- WKT indexing and lookup consume these read-only results.
- Harness parsing, relation JSON and terminal output live elsewhere.

'''

from pathlib import Path

from ._commands import query


def repository(path: str) -> tuple[Path, dict[str, str]]:
    '''
    Find the common Git directory and verified linked WKTs.

    - Return `(common_dir, {absolute_wkt_root: private_git_dir})`.
    - Exclude the main checkout; callers use `primary_worktree()` for
      it.
    - Require worktree registration, the WKT's .git file and the
      private gitdir backlink to agree. Skip removed/substituted
      WKTs.
    - Reject an inaccessible repository with its queried path.
    - `WktIndexer` and relation writers use this inventory to
      validate observations before recording them. No Git metadata is
      changed.

    '''
    cwd: str = str(Path(path).expanduser().resolve())
    output: str|None = query(
        cwd, 'rev-parse', '--path-format=absolute',
        '--git-common-dir',
    )
    if not output:
        raise ValueError(f'Cannot resolve Git repository: {cwd!r}')

    common: Path = Path(output.rstrip('\n')).resolve()
    roots: set[str] = set(worktree_roots(cwd))
    result: dict[str, str] = {}
    admin: Path
    for admin in (common / 'worktrees').glob('*'):
        try:
            gitfile: Path = Path(
                (admin / 'gitdir').read_text().rstrip('\n'),
            )
            root: Path = gitfile.parent
            if (
                str(root) not in roots
                or
                gitfile.name != '.git'
                or
                not root.is_dir()
                or
                gitfile.is_symlink()
                or
                admin.is_symlink()
            ):
                continue

            # Git stores the backlink in the WKT's .git file. A moved
            # or replaced directory must not inherit its old
            # relation.
            back: str = gitfile.read_text().strip()
            if not back.startswith('gitdir: '):
                continue
            target: Path = (root / back[len('gitdir: '):]).resolve()
            if target != admin.resolve():
                continue
            result[str(root.resolve())] = str(target)

        except OSError:
            continue

    return common, result


def worktree_roots(path: str) -> list[str]:
    '''
    List Git-registered checkout paths, with the main path first.

    - `repository()` uses this registration list for backlink checks.
    - `primary_worktree()` uses its first entry when Git has no
      explicit checkout root, including the bare-repository case.
    - Prunable paths may appear; registration alone does not prove
      that a directory is still present.
    - Raise with the queried path when Git cannot enumerate
      worktrees.

    '''
    cwd: str = str(Path(path).expanduser().resolve())
    listing: str|None = query(
        cwd, 'worktree', 'list', '--porcelain', '-z',
    )
    if listing is None:
        raise ValueError(
            f'Cannot enumerate registered worktrees: {cwd!r}'
        )
    field: str
    return [
        field[len('worktree '):]
        for field in listing.split('\0')
        if field.startswith('worktree ')
    ]


def primary_worktree(common: Path) -> Path:
    '''
    Find the stable main-checkout or bare-repository root.

    - Prefer Git's configured checkout root, then its first
      registered path. Do not infer this from common.parent: separate
      Git dirs and bare layouts have different directory
      relationships.
    - Reject a non-bare layout with no identifiable main .git entry;
      the operator can configure core.worktree for a separate Git
      dir.
    - `wkt._relations.relation_dir()` places shared .ai/state/dialogs
      here, so removing a linked WKT does not remove its relations.

    '''
    common_text: str = str(common)
    roots: list[str] = worktree_roots(common_text)
    if not roots:
        raise ValueError(
            f'Cannot locate the main Git worktree: {common_text!r}'
        )
    configured: str|None = query(
        str(common), 'rev-parse', '--show-toplevel',
    )
    root_text: str = roots[0]
    if configured:
        root_text = configured.rstrip('\n')

    root: Path = Path(root_text).resolve()
    bare: bool = query(
        str(common), 'rev-parse', '--is-bare-repository',
    ) == 'true\n'
    if (
        not bare
        and
        not (root / '.git').exists()
    ):
        root_text = str(root)
        raise ValueError(
            'Cannot locate main checkout; set core.worktree for '
            f'a separate Git directory before creating a new index; '
            f'common={common_text!r}, root={root_text!r}',
        )
    return root


def checkout_location(cwd: str) -> tuple[str, ...]:
    '''
    Locate the root, private Git directory and common directory.

    - `WktLookup.locations` retains this tuple for each saved cwd
      during one listing; the caller decides when to create a fresh
      lookup.
    - Return an empty tuple for missing directories, non-repositories
      or malformed Git output. Listing can then leave WKT unknown.
    - Query only; do not create directories or change Git metadata.

    '''
    output: str|None = query(
        cwd, 'rev-parse', '--path-format=absolute',
        '--show-toplevel', '--git-dir', '--git-common-dir',
    )
    paths: tuple[str, ...] = tuple((output or '').splitlines())
    # rev-parse emits one line for each of the three requested paths.
    # Partial output must not be mistaken for a complete Git
    # location.
    if len(paths) != 3:
        return ()

    return paths
