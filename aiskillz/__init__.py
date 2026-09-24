# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Convenient public imports for the aiskillz.dialogs API.

Import from `aiskillz` for dialog discovery and WKT relations.
Implementation is layered as dialogs -> wkt -> git;
cli.py handles shell arguments and display, while _xontrib.py adapts
Xonsh streams.

'''

from .dialogs import (
    list_dialogs as list_dialogs,
    get_dialog as get_dialog,
    name2id as name2id,
    list_wkt_relations as list_wkt_relations,
    record_wkt_relation as record_wkt_relation,
    preview_wkt_relations as preview_wkt_relations,
    save_wkt_preview as save_wkt_preview,
    apply_wkt_preview as apply_wkt_preview,
)

# Preserve imports from the first local WKT indexing prototype.
list_worktree_associations = list_wkt_relations
record_worktree = record_wkt_relation
preview_worktree_associations = preview_wkt_relations
save_worktree_preview = save_wkt_preview
apply_worktree_preview = apply_wkt_preview
