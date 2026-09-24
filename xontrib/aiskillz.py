# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Expose aiskillz to Xonsh's namespace-based extension discovery.

'''

from aiskillz._xontrib import (
    _load_xontrib_ as _load_xontrib_,
    _unload_xontrib_ as _unload_xontrib_,
)
