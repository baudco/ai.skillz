# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Shared presentation limits used by listing and resume selection.

`cli.format_dialog_table()` shortens only the displayed name. The
resume selector recognizes that same shortened spelling when unique;
metadata records and completion candidates keep the original name.

'''

DIALOG_NAME_WIDTH: int = 36
DIALOG_NAME_ELLIPSIS: str = '…'
