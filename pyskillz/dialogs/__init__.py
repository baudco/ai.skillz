# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Dialog APIs for workspace callers and the ai.dlogs CLI.

Use `list_dialogs()`, `get_dialog()` and `name2id()` for harness
metadata. The WKT functions expose the same relation workflow used
by `/open-wkt` and `ai.dlogs index`, without a shell or terminal
formatter.

'''

from ._api import (
    list_dialogs as list_dialogs,
    get_dialog as get_dialog,
    name2id as name2id,
    preview_wkt_relations as preview_wkt_relations,
)
from ..wkt import (
    list_wkt_relations as list_wkt_relations,
    record_wkt_relation as record_wkt_relation,
    save_wkt_preview as save_wkt_preview,
    apply_wkt_preview as apply_wkt_preview,
)
