'''
Check a completed Claude Code or Codex answer at its Stop hook.

'''
import json
import os
from pathlib import Path
import sys

from code_refs import git_root, validate_response


def stop_decision(data: dict) -> dict:
    '''
    Block an invalid answer so the agent can correct its citations.

    '''
    text = data.get('last_assistant_message')
    if not isinstance(text, str):
        return {'systemMessage': (
            'No last_assistant_message was available; '
            'citation validation was not possible'
        )}
    directory = os.environ.get('AI_SKILLZ_REPLY_ROOT')
    if not directory:
        directory = data.get('cwd')
    root = git_root(Path(directory)) if directory else None
    problems = validate_response(text, root, absolute_only=True)
    if not problems:
        return {}
    details = '\n'.join(problems[:10])
    return {
        'decision': 'block',
        'reason': (
            'Fix editor-jumpable citations before responding. '
            'Use verified absolute path:line references; '
            'do not shorten cross-worktree paths.\n'
            f'{details}'
        ),
    }


def main() -> int:
    '''
    Read Stop JSON on stdin and write one decision on stdout.

    '''
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError('Stop payload must be an object')
        decision = stop_decision(data)
    except (ValueError, OSError) as exc:
        decision = {
            'decision': 'block',
            'reason': f'Could not validate final citations: {exc}',
        }
    print(json.dumps(decision))
    return 0


if __name__ == '__main__':
    sys.exit(main())
