# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Public offline dialog discovery for workspace and picker callers.

Use `list_dialogs(path=..., harness=...)` to select metadata records,
`name2id()` for name-based picker choices, or `get_dialog(id)` when
only an opaque dialog ID is known. All three read local harness
stores; none starts or resumes a harness instance. `docs/pyskillz.md`
describes record fields, eligibility and installation for callers.

'''

from ._dlogs import (
    get_dialog as get_dialog,
    name2id as name2id,
    list_dialogs as list_dialogs,
)
