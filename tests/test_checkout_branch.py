# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise the public branch query used by executor bindings.

'''

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aiskillz.git import checkout_branch


class CheckoutBranchTests(unittest.TestCase):
    '''
    Keep branch observations subject to shared Git query isolation.

    '''

    def test_branch_ignores_inherited_git_directory(self) -> None:
        '''
        A caller's GIT_DIR can redirect raw branch queries elsewhere.
        Initialize a disposable repo, set an invalid override only
        for observation, and prove the shared query still returns
        that repository's branch without changing process state.

        '''
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            subprocess.run(
                ['git', 'init', '-b', 'selected', str(root)],
                check=True, capture_output=True,
            )
            with patch.dict(os.environ, {
                'GIT_DIR': str(root / 'missing'),
            }):
                self.assertEqual(
                    checkout_branch(str(root)), 'selected',
                )

    def test_detached_and_unavailable_are_unknown(self) -> None:
        '''
        An unavailable query must not invent a branch identity.
        Use the public function with a missing directory and model
        a detached HEAD through the same query boundary. Both return
        None, while the query retains its read-only symbolic-ref args.

        '''
        self.assertIsNone(checkout_branch('/nonexistent/aiskillz'))
        with patch('aiskillz.git._discovery.query', return_value=None) \
                as query:
            self.assertIsNone(checkout_branch('/selected'))
        query.assert_called_once_with(
            '/selected', 'symbolic-ref', '--quiet', '--short', 'HEAD',
        )
