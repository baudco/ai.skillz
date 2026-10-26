# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

# Checkout-local development entry point:
# - `source /checkout/aliases.xsh` tries this tree without
#   changing the editable installation or requiring a new shell.
# - Keep this file at the checkout root so switching worktrees only
#   changes the source path. Packaged users load `xontrib aiskillz`.
# - The CLI uses this shell's interpreter. Completion loads the
#   checkout adapter separately, so an older imported package cannot
#   silently redirect the suggestions to another tree.
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
