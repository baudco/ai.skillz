# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Read-only repository discovery used by the worktree layer.

Replace Git CLI discovery here when qualifying Dulwich; callers in
`aiskillz.wkt` depend on these values rather than command output.

'''

from ._discovery import (
    repository as repository,
    worktree_roots as worktree_roots,
    primary_worktree as primary_worktree,
    checkout_location as checkout_location,
)
