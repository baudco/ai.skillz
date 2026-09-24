# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Xonsh integration; loading never scans harness session stores.

'''

from contextlib import redirect_stderr, redirect_stdout
import os
import sys
from typing import Any, TextIO


def dlogs_alias(
    args: list[str],
    stdin: TextIO|None = None,
    stdout: TextIO|None = None,
    stderr: TextIO|None = None,
) -> int:
    '''
    Run `ai.dlogs` inside Xonsh without spawning another Python.

    `_load_xontrib_()` registers this callable. Forward Xonsh's
    output streams for redirects and capture. Convert argparse exits
    to shell statuses so help or invalid arguments cannot exit Xonsh.
    `stdin` is accepted for the alias protocol; discovery does not
    consume it. The loader marks this alias unthreadable because
    redirecting Python's global streams must run on the shell thread.
    Temporarily mirror Xonsh environment overrides into os.environ so
    harness store paths behave as they did with the subprocess alias.

    '''
    from xonsh.built_ins import XSH

    from .cli import main

    output: TextIO = stdout if stdout is not None else sys.stdout
    errors: TextIO = stderr if stderr is not None else sys.stderr
    previous: dict[str, str] = dict(os.environ)
    environment: dict[str, str] = (
        XSH.env.detype() if XSH.env is not None else previous
    )
    try:
        os.environ.clear()
        os.environ.update(environment)
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                return main(args)
            except SystemExit as error:
                return int(error.code or 0)
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _load_xontrib_(xsh: Any, **kwargs: Any) -> dict:
    '''
    Register the in-process alias and remember its prior binding.

    '''
    from xonsh.tools import unthreadable

    command: Any = unthreadable(dlogs_alias)
    previous: Any = xsh.aliases.get('ai.dlogs')
    xsh.ctx['_pyskillz_alias_previous'] = previous
    xsh.ctx['_pyskillz_alias_command'] = command
    xsh.aliases['ai.dlogs'] = command
    resume: list[str] = [
        sys.executable, '-m', 'pyskillz', 'resume',
    ]
    xsh.ctx['_pyskillz_resume_previous'] = (
        xsh.aliases.get('ai.resume')
    )
    xsh.ctx['_pyskillz_resume_command'] = resume
    xsh.aliases['ai.resume'] = resume
    return {}


def _unload_xontrib_(xsh: Any, **kwargs: Any) -> None:
    '''
    Restore the prior alias only if this extension still owns it.

    '''
    command: Any = xsh.ctx.pop(
        '_pyskillz_alias_command', None,
    )
    previous: Any = xsh.ctx.pop('_pyskillz_alias_previous', None)
    if xsh.aliases.get('ai.dlogs') == command:
        if previous is None:
            xsh.aliases.pop('ai.dlogs', None)
        else:
            xsh.aliases['ai.dlogs'] = previous
    resume: Any = xsh.ctx.pop(
        '_pyskillz_resume_command', None,
    )
    prior_resume: Any = xsh.ctx.pop(
        '_pyskillz_resume_previous', None,
    )
    if xsh.aliases.get('ai.resume') == resume:
        if prior_resume is None:
            xsh.aliases.pop('ai.resume', None)
        else:
            xsh.aliases['ai.resume'] = prior_resume
