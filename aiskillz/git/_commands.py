# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Execute the read-only Git queries used by aiskillz.git discovery.

- Keep subprocess invocation and environment isolation in this
  module.
- A future `dulwich` backend can replace discovery internals while
  dialogs/WKT callers continue consuming the same Python results.

'''

import os
from pathlib import Path
import subprocess


# Discovery is interactive metadata lookup, not a long-running Git
# op.
_GIT_QUERY_TIMEOUT_SECONDS: int = 2


def query(cwd: str, *args: str) -> str|None:
    '''
    Run a read-only Git discovery command and return its stdout.

    - `git._discovery` supplies argv and interprets the returned
      text.
    - Require an absolute `cwd`; do not inherit shell directory
      scope.
    - Remove inherited GIT_* variables so another index or repository
      cannot redirect discovery. Leave the caller's environment
      intact.
    - Bound the subprocess by `_GIT_QUERY_TIMEOUT_SECONDS`.
    - Return None for a bad cwd, inaccessible Git, failed command or
      timeout; the discovery caller chooses whether absence is an
      error.

    '''
    if not Path(cwd).is_absolute():
        return None

    key: str
    value: str
    env: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith('GIT_')
    }
    try:
        result: subprocess.CompletedProcess = subprocess.run(
            [
                'git',
                *args,
            ],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=_GIT_QUERY_TIMEOUT_SECONDS,
            check=True,
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return None

    return result.stdout
