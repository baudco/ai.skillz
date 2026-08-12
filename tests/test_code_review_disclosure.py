import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / 'skills'
    / 'code-review'
    / 'scripts'
    / 'finalize-review.py'
)
SPEC = importlib.util.spec_from_file_location(
    'code_review_disclosure',
    SCRIPT,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('unable to load disclosure helper')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CodeReviewDisclosureTests(unittest.TestCase):
    def test_findings_body_contains_one_footer(self):
        '''
        Findings reviews previously reached approval without disclosure.

        This test finalizes a findings-first body and proves the content
        layer appends exactly one active harness/model/provider footer.

        '''
        body = '### [P1] Fix race\n\nEvidence: ...\n'
        result = MODULE.finalize(
            body,
            'opencode',
            'gpt-5.6-sol',
            'openai',
        )
        self.assertEqual(result.count('(this review was generated'), 1)
        self.assertIn(
            '`opencode` using `gpt-5.6-sol`\n(`openai`)',
            result,
        )

    def test_no_findings_footer_is_digest_bound(self):
        '''
        No-findings bodies had the same omission as findings reviews.

        This test hashes the finalized bytes and proves the digest differs
        from the undisclosed body while containing exactly one footer.

        '''
        body = 'No actionable findings.\n\nResidual risks: none.\n'
        result = MODULE.finalize(body, 'claude', 'sonnet', 'anthropic')
        original = hashlib.sha256(body.encode()).hexdigest()
        final = hashlib.sha256(result.encode()).hexdigest()
        self.assertNotEqual(final, original)
        self.assertEqual(result.count('(this review was generated'), 1)

    def test_refinalization_replaces_footer_without_duplicate(self):
        '''
        Candidate updates must not accumulate stale attribution footers.

        This test finalizes twice with changed runtime identity and proves
        the new exact body contains one footer and no stale model value.

        '''
        first = MODULE.finalize('No actionable findings.\n', 'a', 'b', 'c')
        result = MODULE.finalize(first, 'x', 'y', 'z')
        self.assertEqual(result.count('(this review was generated'), 1)
        self.assertNotIn('`a` using `b` (`c`)', result)
        self.assertIn('`x` using `y` (`z`)', result)

    def test_all_prior_footers_are_replaced(self):
        '''
        Wrapped duplicate footers could survive an update and be published.

        This test supplies duplicates wrapped at different phrase boundaries
        and proves finalization removes all of them before appending one.

        '''
        body = (
            'No actionable findings.\n\n'
            '(this review was generated in some part by `a` using\n'
            '`b` (`c`))\n\n'
            '(this review was generated in some part\n'
            'by `d` using `e` (`f`))\n'
        )
        result = MODULE.finalize(body, 'x', 'y', 'z')
        self.assertEqual(result.count('(this review was generated'), 1)
        self.assertNotIn('`a`', result)
        self.assertNotIn('`d`', result)

    def test_cli_persists_footer_before_digest(self):
        '''
        Publication candidates must bind approval to disclosed bytes.

        This test runs the content-layer CLI, reads the persisted candidate,
        and proves its printed digest hashes the body including one footer.

        '''
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / 'review.md'
            path.write_text('No actionable findings.\n')
            with mock.patch('builtins.print') as output:
                result = MODULE.main(
                    [
                        '--body-file', str(path),
                        '--harness', 'opencode',
                        '--model', 'gpt',
                        '--provider', 'openai',
                    ]
                )
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            self.assertEqual(result, 0)
            output.assert_called_once_with(digest)
            self.assertEqual(payload.count(b'(this review was generated'), 1)

    def test_other_content_contracts_remain_separate(self):
        '''
        Top-level disclosure must not replace existing reply attribution.

        This test inspects the canonical contracts and proves review replies
        retain their quote format while JSON remains disclosure-free.

        '''
        reply_skill = (
            ROOT / 'skills' / 'code-review-changes' / 'SKILL.md'
        ).read_text()
        schema = (
            ROOT
            / 'skills'
            / 'code-review'
            / 'references'
            / 'review-result-v1.schema.json'
        ).read_text()
        self.assertIn('> response authored by `<harness>`', reply_skill)
        self.assertNotIn('this review was generated', reply_skill)
        self.assertNotIn('this review was generated', schema)


if __name__ == '__main__':
    unittest.main()
