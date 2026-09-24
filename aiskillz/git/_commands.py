# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Execute read-only Git commands for `aiskillz.git` discovery.

Keep subprocess invocation and environment isolation here. A future
Dulwich backend replaces this implementation behind the discovery
functions; dialogs and worktree indexing consume their Python values.

'''

import os
from pathlib import Path
import subprocess


def query(cwd: str, *args: str) -> str|None:
    '''
    Run a read-only Git command at an absolute directory.

    The discovery module supplies Git arguments and parses stdout.
    Remove inherited GIT_* variables so shell index/repository
    overrides cannot redirect these queries. Return None on invalid
    cwd, failed commands, inaccessible directories or the two-second
    timeout.

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
            ['git', *args], cwd=cwd, env=env,
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return None
    return result.stdout
