# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Inspect repositories and registered worktrees through Git.

This layer owns Git paths, worktree registration and backlink checks.
It knows nothing about harness dialogs, association JSON or terminal
output. Worktree indexing and lookup consume these query results.

'''

from pathlib import Path

from ._commands import query


def repository(path: str) -> tuple[Path, dict[str, str]]:
    '''
    Return the common Git directory and live linked-worktree paths.

    The mapping is absolute worktree root -> private Git directory.
    Exclude the main checkout. Association recording and preview
    apply use it to verify a worktree still exists and belongs to
    this repo. Git registration, the worktree .git file and the
    private gitdir backlink must agree. Skip removed or substituted
    worktrees; reject an inaccessible repository. This function only
    reads Git metadata.

    '''
    cwd: str = str(Path(path).expanduser().resolve())
    output: str|None = query(
        cwd, 'rev-parse', '--path-format=absolute',
        '--git-common-dir',
    )
    if not output:
        raise ValueError('Cannot resolve Git repository: ' + cwd)
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
            back: str = gitfile.read_text().strip()
            if not back.startswith('gitdir: '):
                continue
            target: Path = (root / back[8:]).resolve()
            if target != admin.resolve():
                continue
            result[str(root.resolve())] = str(target)
        except OSError:
            continue
    return common, result


def worktree_roots(path: str) -> list[str]:
    '''
    Return Git-registered checkout paths, with the main path first.

    `repository()` uses these paths to check registration, and
    `primary_worktree()` uses the first entry when core.worktree
    is unset. Prunable paths may be returned;
    `repository()` separately verifies live linked checkouts.

    '''
    cwd: str = str(Path(path).expanduser().resolve())
    listing: str|None = query(
        cwd, 'worktree', 'list', '--porcelain', '-z',
    )
    if listing is None:
        raise ValueError('Cannot enumerate registered worktrees')
    field: str
    return [
        field[len('worktree '):]
        for field in listing.split('\0')
        if field.startswith('worktree ')
    ]


def primary_worktree(common: Path) -> Path:
    '''
    Resolve the main checkout, or bare repo directory, using Git.

    `wkt._relations.relation_dir()` appends .ai/state/dialogs
    here so every linked checkout shares the same association file.
    Query Git rather than assuming common.parent: separate Git dirs
    and bare repositories do not have that filesystem layout.

    '''
    roots: list[str] = worktree_roots(str(common))
    if not roots:
        raise ValueError('Cannot locate the main Git worktree')
    configured: str|None = query(
        str(common), 'rev-parse', '--show-toplevel',
    )
    root: Path = Path(
        configured.rstrip('\n') if configured else roots[0],
    ).resolve()
    bare: bool = query(
        str(common), 'rev-parse', '--is-bare-repository',
    ) == 'true\n'
    if (
        not bare
        and
        not (root / '.git').exists()
    ):
        raise ValueError(
            'Cannot locate main checkout; set core.worktree for '
            'a separate Git directory before creating a new index',
        )
    return root


def checkout_location(cwd: str) -> tuple[str, ...]:
    '''
    Return root, private Git dir and common Git dir for a saved cwd.

    `WktLookup` caches this result while assembling dialog rows.
    Return an empty tuple for missing directories, non-repositories
    or invalid cwd values; callers then leave the worktree unknown.

    '''
    output: str|None = query(
        cwd, 'rev-parse', '--path-format=absolute',
        '--show-toplevel', '--git-dir', '--git-common-dir',
    )
    paths: tuple[str, ...] = tuple((output or '').splitlines())
    return paths if len(paths) == 3 else ()
