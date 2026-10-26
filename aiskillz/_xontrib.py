# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Xonsh integration; loading never scans harness session stores.

'''

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
import os
import sys
from typing import TextIO

from xonsh.built_ins import XonshSession


def dlogs_alias(
    args: list[str],
    stdin: TextIO|None = None,
    stdout: TextIO|None = None,
    stderr: TextIO|None = None,
) -> int:
    '''
    Run `ai.dlogs` inside Xonsh without spawning another Python.

    `_load_xontrib_()` installs this callable as `ai.dlogs`.

    - Forward stdout/stderr so shell redirects and capture work.
    - Turn argparse's SystemExit into an exit status, not shell exit.
    - Accept stdin for Xonsh's alias protocol; discovery does not
      read it.
    - Mark the alias unthreadable: redirect_stdout/redirect_stderr
      temporarily change process-wide streams, so use the shell
      thread.
    - Mirror Xonsh's environment into os.environ for the duration of
      the call, then restore it even on failure. Shell-only
      CODEX_HOME or OPENCODE_DATA_DIR changes must select the same
      files as subprocess aliases do, without leaking the temporary
      environment afterward.

    '''
    from xonsh.built_ins import XSH

    from .cli import main

    output: TextIO = sys.stdout
    if stdout is not None:
        output = stdout

    errors: TextIO = sys.stderr
    if stderr is not None:
        errors = stderr

    previous: dict[str, str] = dict(os.environ)
    environment: dict[str, str] = previous
    if XSH.env is not None:
        environment = XSH.env.detype()

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


def _load_xontrib_(xsh: XonshSession, **kwargs: object) -> dict:
    '''
    Register the in-process alias and remember its prior binding.

    Repeated loads retain the first saved binding while the current
    alias is still owned by this extension. A user replacement
    becomes the prior binding when a subsequent load takes it over.

    '''
    from xonsh.tools import unthreadable
    from ._completion import register_resume_completer

    command: object = unthreadable(dlogs_alias)
    if (
        '_aiskillz_alias_command' not in xsh.ctx
        or
        xsh.aliases.get('ai.dlogs')
        != xsh.ctx['_aiskillz_alias_command']
    ):
        xsh.ctx['_aiskillz_alias_previous'] = (
            xsh.aliases.get('ai.dlogs')
        )
    xsh.ctx['_aiskillz_alias_command'] = command
    xsh.aliases['ai.dlogs'] = command
    resume: list[str] = [
        sys.executable,
        '-m',
        'aiskillz',
        'resume',
    ]
    if (
        '_aiskillz_resume_command' not in xsh.ctx
        or
        xsh.aliases.get('ai.resume')
        != xsh.ctx['_aiskillz_resume_command']
    ):
        xsh.ctx['_aiskillz_resume_previous'] = (
            xsh.aliases.get('ai.resume')
        )
    xsh.ctx['_aiskillz_resume_command'] = resume
    xsh.aliases['ai.resume'] = resume
    register_resume_completer(xsh)
    return {}


def _unload_xontrib_(xsh: XonshSession, **kwargs: object) -> None:
    '''
    Restore the prior alias only if this extension still owns it.

    '''
    from ._completion import unregister_resume_completer

    unregister_resume_completer(xsh)
    command: object = xsh.ctx.pop(
        '_aiskillz_alias_command', None,
    )
    previous: object = xsh.ctx.pop('_aiskillz_alias_previous', None)
    if xsh.aliases.get('ai.dlogs') == command:
        if previous is None:
            xsh.aliases.pop('ai.dlogs', None)
        else:
            xsh.aliases['ai.dlogs'] = previous
    resume: object = xsh.ctx.pop(
        '_aiskillz_resume_command', None,
    )
    prior_resume: object = xsh.ctx.pop(
        '_aiskillz_resume_previous', None,
    )
    if xsh.aliases.get('ai.resume') == resume:
        if prior_resume is None:
            xsh.aliases.pop('ai.resume', None)
        else:
            xsh.aliases['ai.resume'] = prior_resume
