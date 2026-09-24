# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Manage worktree relations using the read-only Git layer.

WktIndexer consumes supplied dialog records; WktLookup
reads existing relations. Dialog orchestration supplies harness
readers, so this package depends on git but never on dialogs or the
CLI.

'''

from ._indexer import WktIndexer as WktIndexer
from ._lookup import WktLookup as WktLookup
from ._relations import (
    list_wkt_relations as list_wkt_relations,
)
from ._operations import (
    record_wkt_relation as record_wkt_relation,
    save_wkt_preview as save_wkt_preview,
    apply_wkt_preview as apply_wkt_preview,
)
