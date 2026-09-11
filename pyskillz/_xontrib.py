# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Xonsh integration; loading never scans harness session stores.

'''

import sys
from typing import Any


def _load_xontrib_(xsh: Any, **kwargs: Any) -> dict:
    '''
    Register the CLI using the interpreter that loaded this package.

    '''
    command: list[str] = [sys.executable, '-m', 'pyskillz']
    previous: Any = xsh.aliases.get('ai.dlogs')
    xsh.ctx['_pyskillz_alias_previous'] = previous
    xsh.ctx['_pyskillz_alias_command'] = command
    xsh.aliases['ai.dlogs'] = command
    return {}


def _unload_xontrib_(xsh: Any, **kwargs: Any) -> None:
    '''
    Restore the prior alias only if this extension still owns it.

    '''
    command: list[str]|None = xsh.ctx.pop(
        '_pyskillz_alias_command', None,
    )
    previous: Any = xsh.ctx.pop('_pyskillz_alias_previous', None)
    if xsh.aliases.get('ai.dlogs') == command:
        if previous is None:
            xsh.aliases.pop('ai.dlogs', None)
        else:
            xsh.aliases['ai.dlogs'] = previous
