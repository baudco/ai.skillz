'''
Query the planner's existing index evidence without dynamic code.

'''

import importlib.util
import json
from pathlib import Path
import sys


def main():
    '''
    Compare a snapshot or prepared initial evidence, without staging.

    '''
    source = (
        Path(__file__).resolve().parents[1]
        / 'skills/commit-plan/scripts/plan-build.py'
    )
    spec = importlib.util.spec_from_file_location('planner', source)
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    evidence, _ = planner.snapshot(Path.cwd())
    print(json.dumps(evidence, indent=2))
    if len(sys.argv) > 1:
        expected = json.loads(Path(sys.argv[1]).read_bytes())
        expected = expected.get('initial', expected)
        return int(evidence != expected)
    return 0


if __name__ == '__main__':
    sys.exit(main())
