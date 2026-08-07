import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / 'skills'
    / 'opencode-cleaning'
    / 'scripts'
    / 'opencode-cleaning.py'
)
SPEC = importlib.util.spec_from_file_location(
    'opencode_cleaning',
    SCRIPT,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(
        'unable to load opencode-cleaning helper'
    )
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class OpenCodeCleaningTests(unittest.TestCase):
    def session(
        self,
        session_id: str,
        title: str,
        directory: str,
        updated: int,
    ):
        return MODULE.Session(
            id=session_id,
            title=title,
            directory=directory,
            updated=updated,
        )

    def test_full_fork_title_pattern(self):
        self.assertIsNotNone(
            MODULE.FORK_TITLE.fullmatch(
                'work (fork #1)'
            )
        )
        self.assertIsNotNone(
            MODULE.FORK_TITLE.fullmatch(
                'work (fork #12)'
            )
        )
        self.assertIsNone(
            MODULE.FORK_TITLE.fullmatch(
                'work (fork #0)'
            )
        )
        self.assertIsNone(
            MODULE.FORK_TITLE.fullmatch('(fork #1)')
        )
        self.assertIsNone(
            MODULE.FORK_TITLE.fullmatch(
                'work (fork #1) extra'
            )
        )

    def test_selection_is_bounded_and_stale(self):
        day = MODULE.DAY_MS
        now = 20 * day
        sessions = (
            self.session('new', 'main', '/repo', now),
            self.session(
                'old-fork',
                'main (fork #1)',
                '/repo',
                now - 10 * day,
            ),
            self.session(
                'fresh-fork',
                'main (fork #2)',
                '/repo',
                now - day,
            ),
            self.session(
                'other',
                'main (fork #3)',
                '/other',
                now - 15 * day,
            ),
            self.session(
                'not-fork',
                'historical',
                '/repo',
                now - 15 * day,
            ),
        )
        selected = MODULE.select_sessions(
            sessions,
            '/repo',
            older_than_days=7,
            now_ms=now,
        )
        self.assertEqual(selected.protected.id, 'new')
        self.assertEqual(
            [item.id for item in selected.candidates],
            ['old-fork'],
        )

    def test_newest_fork_is_always_protected(self):
        day = MODULE.DAY_MS
        now = 30 * day
        sessions = (
            self.session(
                'active-fork',
                'main (fork #2)',
                '/repo',
                now - 8 * day,
            ),
            self.session(
                'older-fork',
                'main (fork #1)',
                '/repo',
                now - 10 * day,
            ),
        )
        selected = MODULE.select_sessions(
            sessions,
            '/repo',
            older_than_days=7,
            now_ms=now,
        )
        self.assertEqual(
            selected.protected.id,
            'active-fork',
        )
        self.assertEqual(
            [item.id for item in selected.candidates],
            ['older-fork'],
        )

    def test_token_changes_with_candidate_metadata(self):
        session = self.session(
            'fork',
            'main (fork #1)',
            '/repo',
            10,
        )
        first = MODULE.Selection(
            directory='/repo',
            older_than_days=7,
            protected=None,
            candidates=(session,),
        )
        second = MODULE.Selection(
            directory='/repo',
            older_than_days=7,
            protected=None,
            candidates=(
                self.session(
                    'fork',
                    'main (fork #1)',
                    '/repo',
                    11,
                ),
            ),
        )
        self.assertNotEqual(
            MODULE.selection_token(first),
            MODULE.selection_token(second),
        )

    def test_token_ignores_protected_session_activity(self):
        first = MODULE.Selection(
            directory='/repo',
            older_than_days=7,
            protected=self.session(
                'active',
                'main',
                '/repo',
                10,
            ),
            candidates=(),
        )
        second = MODULE.Selection(
            directory='/repo',
            older_than_days=7,
            protected=self.session(
                'active',
                'main',
                '/repo',
                11,
            ),
            candidates=(),
        )
        self.assertEqual(
            MODULE.selection_token(first),
            MODULE.selection_token(second),
        )

    def test_non_finite_age_is_not_a_valid_threshold(self):
        self.assertFalse(MODULE.valid_age(float('nan')))
        self.assertFalse(MODULE.valid_age(float('inf')))
        self.assertFalse(MODULE.valid_age(-1))
        self.assertTrue(MODULE.valid_age(0))


if __name__ == '__main__':
    unittest.main()
