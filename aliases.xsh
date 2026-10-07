# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

# The source entrypoint needs no installation; packaged users can run
# `xontrib load aiskillz` instead.
import pathlib as _skillz_pathlib
import sys as _skillz_sys
import runpy as _skillz_runpy

_skillz_cli = str(
    _skillz_pathlib.Path(__file__).resolve().parent
    / 'aiskillz' / 'cli.py'
)
aliases['ai.dlogs'] = [
    _skillz_sys.executable,
    _skillz_cli,
]
aliases['ai.resume'] = [
    _skillz_sys.executable,
    _skillz_cli,
    'resume',
]
_skillz_completion = _skillz_runpy.run_path(str(
    _skillz_pathlib.Path(__file__).resolve().parent
    / 'aiskillz' / '_completion.py'
))
_skillz_completion['register_resume_completer'](__xonsh__)
del _skillz_cli, _skillz_pathlib, _skillz_sys
del _skillz_completion, _skillz_runpy
