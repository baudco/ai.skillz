import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LINKIFY = (
    ROOT / 'skills' / 'pr-msg' / 'scripts' / 'linkify-commits.py'
)
SPEC = importlib.util.spec_from_file_location(
    'linkify_commits',
    LINKIFY,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('unable to load commit linkifier')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def load_merge_helpers():
    source = (
        ROOT / 'skills' / 'pr-msg' / 'pr-merge.xsh'
    ).read_text()
    namespace = {'aliases': {}}
    exec(compile(source, 'pr-merge.xsh', 'exec'), namespace)
    return namespace


class PrMsgHelperTests(unittest.TestCase):
    def test_merge_flags_are_not_consumed_as_the_base(self):
        '''
        A second-position merge flag was treated as a Git base.

        The helper generated an invalid revision range and omitted
        the requested merge mode. This test replaces linkification
        and GitHub execution, proving the flag reaches only merge.

        '''
        namespace = load_merge_helpers()
        linkify = mock.Mock(return_value=0)
        namespace['_pr_linkify'] = linkify
        with mock.patch.object(
            namespace['_sp'],
            'call',
            return_value=0,
        ) as call:
            result = namespace['_pr_merge'](['7', '--squash'])
        self.assertEqual(result, 0)
        linkify.assert_called_once_with(['7'])
        call.assert_called_once_with(
            ['gh', 'pr', 'merge', '7', '--squash']
        )

    def test_explicit_base_is_separate_from_merge_flags(self):
        '''
        An explicit base must still be available for stacked PRs.

        This test supplies a base and two merge options. The mocks
        prove linkification consumes only the base while GitHub
        receives both options in their original order.

        '''
        namespace = load_merge_helpers()
        linkify = mock.Mock(return_value=0)
        namespace['_pr_linkify'] = linkify
        with mock.patch.object(
            namespace['_sp'],
            'call',
            return_value=0,
        ) as call:
            result = namespace['_pr_merge'](
                ['7', 'develop', '--merge', '--delete-branch']
            )
        self.assertEqual(result, 0)
        linkify.assert_called_once_with(['7', 'develop'])
        call.assert_called_once_with(
            [
                'gh', 'pr', 'merge', '7', '--merge',
                '--delete-branch',
            ]
        )

    def test_linkifier_accepts_ssh_url_remotes(self):
        '''
        Fully qualified SSH remotes previously failed URL detection.

        The fixture presents the common ssh:// Git URL form. Mocking
        remote listing isolates parsing and proves links use HTTPS
        repository base without retaining the Git suffix.

        '''
        cases = (
            (
                'ssh://git@forge.example/owner/repo.git',
                'https://forge.example/owner/repo',
            ),
            (
                'ssh://git@forge.example:2222/owner/repo.git',
                'https://forge.example/owner/repo',
            ),
            (
                'git@forge.example:owner/repo.git',
                'https://forge.example/owner/repo',
            ),
            (
                'https://forge.example/owner/repo.git',
                'https://forge.example/owner/repo',
            ),
            (
                'https://forge.example:8443/owner/repo.git',
                'https://forge.example:8443/owner/repo',
            ),
        )
        for url, expected in cases:
            with self.subTest(url=url):
                remotes = f'origin {url} (fetch)'
                with mock.patch.object(
                    MODULE,
                    'sh',
                    return_value=remotes,
                ):
                    result = MODULE.detect_repo_url()
                self.assertEqual(
                    result,
                    expected,
                )

    def test_linkifier_rejects_https_credentials(self):
        '''
        Remote credentials must never enter published commit links.

        HTTPS userinfo can contain a username and token separated by a
        colon, which resembles a host port. This fixture proves such a
        remote is rejected instead of returning a credential-bearing URL.

        '''
        remote = (
            'origin https://oauth2:secret@forge.example/'
            'owner/repo.git (fetch)'
        )
        with mock.patch.object(MODULE, 'sh', return_value=remote):
            with self.assertRaisesRegex(
                SystemExit,
                'no parseable',
            ):
                MODULE.detect_repo_url()


if __name__ == '__main__':
    unittest.main()
