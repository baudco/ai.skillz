import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / 'skills'
    / 'commit-plan'
    / 'references'
    / 'receipt-extension.schema.json'
)
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'commit_plan_state.json'


class CommitPlanReceiptSchemaTests(unittest.TestCase):

    def setUp(self):
        self.schema = json.loads(SCHEMA_PATH.read_text())
        self.fixture = json.loads(FIXTURE_PATH.read_text())

    def test_fixture_covers_required_state(self):
        '''
        Prevent an underspecified plan-state fixture.

        Receipt-backed execution previously described a versioned extension
        without defining fields that a later session could validate. This
        compares the fixture at each state-machine layer with the schema's
        required keys, proving that boundary checks, replies and completion
        evidence have concrete persisted representations.

        '''
        required = set(self.schema['required'])
        self.assertTrue(required <= self.fixture.keys())

        boundary_schema = self.schema['$defs']['boundary']
        boundary = self.fixture['boundaries'][0]
        self.assertTrue(set(boundary_schema['required']) <= boundary.keys())

        for name in ('message', 'check', 'review_reply', 'completion'):
            definition = self.schema['$defs'][name]
            value = boundary.get(name)
            if name == 'check':
                value = boundary['checks'][0]
            elif name == 'review_reply':
                value = boundary['review_replies'][0]
            self.assertTrue(set(definition['required']) <= value.keys())

    def test_fixture_preserves_lifecycle_invariants(self):
        '''
        Prevent ambiguous parent and reply lifecycle state.

        The earlier prose allowed execution without a receipt, used no exact
        extension schema and left review resumption implicit. This fixture
        arranges a receipt-less pending boundary with one assigned reply and
        asserts canonical serialization, one parent source, sorted paths and
        states accepted by the schema. Those checks prove a later helper can
        resume from standalone state without inventing discovery policy.

        '''
        boundary = self.fixture['boundaries'][0]
        parent_values = (
            boundary['expected_parent_oid'],
            boundary['expected_parent_boundary_id'],
        )
        self.assertEqual(sum(value is not None for value in parent_values), 1)
        self.assertEqual(boundary['paths'], sorted(boundary['paths']))

        states = self.schema['properties']['state']['enum']
        self.assertIn(self.fixture['state'], states)
        reply_states = self.schema['$defs']['review_reply'][
            'properties'
        ]['status']['enum']
        self.assertIn(boundary['review_replies'][0]['status'], reply_states)

        canonical = json.dumps(
            self.fixture,
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )
        self.assertEqual(json.loads(canonical), self.fixture)


if __name__ == '__main__':
    unittest.main()
