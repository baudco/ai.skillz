# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

# The source entrypoint needs no installation; packaged users can run
# `xontrib load pyskillz` instead.
import pathlib as _skillz_pathlib
import sys as _skillz_sys

aliases['ai.dlogs'] = [
    _skillz_sys.executable,
    str(_skillz_pathlib.Path(__file__).resolve().parent
        / 'pyskillz' / 'cli.py'),
]
del _skillz_pathlib, _skillz_sys
