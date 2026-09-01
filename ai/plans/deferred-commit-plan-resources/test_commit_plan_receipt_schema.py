'''
Historical fixture checks for the deferred receipt-state proposal.

These checks do not validate shipped executor state or implement
the proposed recovery lifecycle. Resource paths were relocated
from the original test when preserving the deferred experiment.

'''
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / 'receipt-extension.schema.json'
FIXTURE_PATH = ROOT / 'commit_plan_state.json'


class CommitPlanReceiptSchemaTests(unittest.TestCase):
    '''
    Preserve structural evidence from the historical proposal.

    '''

    def setUp(self):
        '''
        Load the adjacent historical schema and fixture.

        '''
        self.schema = json.loads(SCHEMA_PATH.read_text())
        self.fixture = json.loads(FIXTURE_PATH.read_text())

    def test_fixture_covers_required_state(self):
        '''
        Prevent an underspecified plan-state fixture.

        Receipt-backed execution previously described a versioned
        extension without defining fields a later session could
        validate. Compare `self.fixture` at each state-machine layer
        with required keys in `self.schema`, showing that boundary
        checks, replies and completion evidence have concrete
        persisted representations in this historical proposal.

        '''
        required = set(self.schema['required'])
        self.assertTrue(required <= self.fixture.keys())

        boundary_schema = self.schema['$defs']['boundary']
        boundary = self.fixture['boundaries'][0]
        self.assertTrue(
            set(boundary_schema['required']) <= boundary.keys(),
        )

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

        The earlier prose allowed execution without a receipt,
        used no exact extension schema and left review resumption
        implicit. `self.fixture` arranges a receipt-less pending
        boundary with one assigned reply. Assert JSON round-tripping,
        one parent source, sorted paths and states from `self.schema`.
        This preserves the proposed recovery inputs without proving
        that a helper implements recovery or validating every schema
        constraint.

        '''
        boundary = self.fixture['boundaries'][0]
        parent_values = (
            boundary['expected_parent_oid'],
            boundary['expected_parent_boundary_id'],
        )
        self.assertEqual(
            sum(value is not None for value in parent_values),
            1,
        )
        self.assertEqual(boundary['paths'], sorted(boundary['paths']))

        states = self.schema['properties']['state']['enum']
        self.assertIn(self.fixture['state'], states)
        reply_states = self.schema['$defs']['review_reply'][
            'properties'
        ]['status']['enum']
        self.assertIn(
            boundary['review_replies'][0]['status'],
            reply_states,
        )

        canonical = json.dumps(
            self.fixture,
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )
        self.assertEqual(json.loads(canonical), self.fixture)


if __name__ == '__main__':
    unittest.main()
