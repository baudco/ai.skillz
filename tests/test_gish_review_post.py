import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / 'skills'
    / 'gish'
    / 'scripts'
    / 'review-post.py'
)
SPEC = importlib.util.spec_from_file_location(
    'gish_review_post',
    SCRIPT,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('unable to load gish review helper')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GishReviewPostTests(unittest.TestCase):
    def target(self, **changes):
        values = {
            'backend': 'gh',
            'repository': 'owner/repo',
            'pr': 7,
            'head': 'abc123',
            'event': 'comment',
            'actor': 'reviewer',
        }
        values.update(changes)
        return MODULE.ReviewTarget(**values)

    def body(self, root: Path) -> tuple[Path, str]:
        path = root / 'review.md'
        payload = b'No actionable findings.\n'
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        return path, digest

    def test_body_is_digest_and_worktree_bound(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            path, digest = self.body(root)
            selected, payload = MODULE.validate_body(
                str(path),
                root,
                digest,
            )
            self.assertEqual(selected, path)
            self.assertEqual(payload, path.read_bytes())
            with self.assertRaisesRegex(
                ValueError,
                'digest changed',
            ):
                MODULE.validate_body(
                    str(path),
                    root,
                    '0' * 64,
                )

    def test_body_symlink_and_external_path_are_refused(self):
        with tempfile.TemporaryDirectory() as first:
            with tempfile.TemporaryDirectory() as second:
                root = Path(first)
                external, digest = self.body(Path(second))
                link = root / 'review.md'
                link.symlink_to(external)
                with self.assertRaisesRegex(
                    ValueError,
                    'must not be a symlink',
                ):
                    MODULE.validate_body(
                        str(link),
                        root,
                        digest,
                    )
                with self.assertRaisesRegex(
                    ValueError,
                    'outside the active worktree',
                ):
                    MODULE.validate_body(
                        str(external),
                        root,
                        digest,
                    )

    def test_only_github_comment_event_is_accepted(self):
        MODULE.validate_target(self.target())
        for changes in (
            {'backend': 'gitea'},
            {'event': 'approve'},
            {'pr': 0},
            {'repository': 'invalid'},
        ):
            with self.assertRaises(ValueError):
                MODULE.validate_target(
                    self.target(**changes)
                )

    def test_head_drift_refuses_post(self):
        response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    'headRefOid': 'different',
                    'state': 'OPEN',
                    'url': 'https://example.invalid/pr/7',
                }
            ),
            stderr='',
        )
        with mock.patch.object(
            MODULE.subprocess,
            'run',
            side_effect=(
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout='secret-token\n',
                    stderr='',
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout='reviewer\n',
                    stderr='',
                ),
                response,
            ),
        ) as run:
            with self.assertRaisesRegex(
                ValueError,
                'head moved',
            ):
                MODULE.publish_github(
                    self.target(),
                    Path('/repo/review.md'),
                    'gh',
                )
        self.assertEqual(run.call_count, 3)

    def test_post_uses_file_and_pinned_comment_event(self):
        responses = (
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='secret-token\n',
                stderr='',
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='reviewer\n',
                stderr='',
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        'headRefOid': 'abc123',
                        'state': 'OPEN',
                        'url': 'https://example.invalid/pr/7',
                    }
                ),
                stderr='',
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        'id': 9,
                        'html_url': (
                            'https://example.invalid/review/9'
                        ),
                    }
                ),
                stderr='',
            ),
        )
        body = Path('/repo/review.md')
        with mock.patch.object(
            MODULE.subprocess,
            'run',
            side_effect=responses,
        ) as run:
            result = MODULE.publish_github(
                self.target(),
                body,
                'gh',
            )
        self.assertEqual(result['id'], 9)
        post = run.call_args_list[3].args[0]
        self.assertIn('event=COMMENT', post)
        self.assertIn('commit_id=abc123', post)
        self.assertIn(f'body=@{body}', post)


if __name__ == '__main__':
    unittest.main()
