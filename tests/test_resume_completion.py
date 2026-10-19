# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Exercise dialog completion through Xonsh's real context parser.

Use synthetic metadata and a disposable Codex SQLite index to prove
selection, quoting, live updates and completer lifecycle behavior.
No harness is launched and no real user dialog store is accessed.

'''

from collections import OrderedDict
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, patch

from xonsh.parsers.completion_context import CompletionContextParser

from aiskillz._completion import (
    complete_resume,
    register_resume_completer,
    unregister_resume_completer,
)
from aiskillz._xontrib import _load_xontrib_, _unload_xontrib_


def completions(line: str, cursor: int|None = None) -> list|set|None:
    '''
    Parse a real command line and invoke the contextual completer.

    '''
    context = CompletionContextParser().parse(
        line, len(line) if cursor is None else cursor,
    )
    result: Any = complete_resume(context)
    return result[0] if isinstance(result, tuple) else result


def test_completion_filters_and_selector_position() -> None:
    '''
    Name suggestions must reflect resume's directory/backend scope.

    Pass filters before and after the selector, including equals
    syntax and an ID disambiguator. Check the actual API arguments
    and ensure option values, later positionals and unrelated
    commands never cause metadata discovery.

    '''
    row: dict = {
        'name': 'Work dialog',
        'id': 'saved-id',
        'harness': 'codex',
        'cwd': '/repo',
    }
    line: str
    expected: dict
    for line, expected in (
        ('ai.resume Wo', {'path': '.', 'harness': None}),
        (
            'ai.resume -a -b cx Wo',
            {'path': None, 'harness': 'cx'},
        ),
        (
            'ai.resume --repo=/repo --harness=cld Wo',
            {'path': '/repo', 'harness': 'cld'},
        ),
        (
            'ai.resume --harness=cld -b cx Wo',
            {'path': '.', 'harness': 'cx'},
        ),
    ):
        with patch(
            'aiskillz._completion.dialogs.list_dialogs',
            return_value=[row],
        ) as listing:
            result: list = completions(line)
            item: Any
            assert {item.display for item in result} == {
                'Work dialog',
            }
            listing.assert_called_once_with(**expected, environ=ANY)
    line = 'ai.resume Wo -a -b cx --id saved-id'
    with patch(
        'aiskillz._completion.dialogs.list_dialogs',
        return_value=[row],
    ) as listing:
        assert completions(line, len('ai.resume Wo'))
        listing.assert_called_once_with(
            path=None, harness='cx', environ=ANY,
        )
    line: str
    for line in (
        'other Wo',
        'ai.resume --repo ',
        'ai.resume -b ',
        'ai.resume --id ',
        'ai.resume --cwd ',
        'ai.resume selected ',
    ):
        with patch(
            'aiskillz._completion.dialogs.list_dialogs',
        ) as listing:
            assert completions(line) is None
            listing.assert_not_called()


def test_completed_names_are_literal_shell_arguments(
    tmp_path: Path,
) -> None:
    '''
    Dialog names can contain syntax and must remain one literal arg.

    Complete a hostile name with spaces, quotes, dollar expansion,
    backslashes and a newline. Test bare and quoted prefixes,
    including an existing closing quote behind the cursor. Execute
    an isolated capture alias in a fresh Xonsh process: its
    argument JSON must exactly equal the original saved name.

    '''
    name: str = 'Odd \'" $HOME $(false) \\ tail\nend'
    row: dict = {
        'name': name,
        'id': 'one',
        'harness': 'claude',
        'cwd': str(tmp_path),
    }
    line: str
    cursor: int
    for line, cursor in (
        ('ai.resume Odd', len('ai.resume Odd')),
        ("ai.resume 'Odd", len("ai.resume 'Odd")),
        ('ai.resume "Odd"', len('ai.resume "Odd"')),
    ):
        with patch(
            'aiskillz._completion.dialogs.list_dialogs',
            return_value=[row],
        ):
            result: list = completions(line, cursor)
        item = next(iter(result))
        completed: str = (
            line[:cursor - item.prefix_len] + str(item)
            + line[cursor:]
        )
        script: str = (
            'import json\n'
            'def capture(args):\n'
            '    print(json.dumps(args))\n'
            'aliases["ai.resume"] = capture\n' + completed
        )
        output = subprocess.run(
            [
                sys.executable,
                '-m',
                'xonsh',
                '--no-rc',
                '-c',
                script,
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        assert json.loads(output.stdout) == [name]


def test_completion_updates_and_shell_environment(
    tmp_path: Path,
) -> None:
    '''
    Completion must use live local metadata and shell-only overrides.

    Seed an isolated Codex database and expose its location only in
    Xonsh's environment. Complete, rename the saved dialog, then
    complete again to prove no stale completion cache is used. Keep
    the process environment byte-for-byte equivalent after lookup.
    Then exercise prompt-toolkit's real alias-expanding frontend
    through both loader paths. The first implementation tested only
    `Completer` directly, missing this expansion and falling back
    to file suggestions when a person actually pressed Tab.
    Seed newer and older names whose alphabetical order disagrees
    with recency. Verify both configured orders at that frontend.

    '''
    from xonsh.built_ins import XSH

    database: Path = tmp_path / 'state_5.sqlite'
    connection: sqlite3.Connection
    with sqlite3.connect(database) as connection:
        connection.execute(
            'CREATE TABLE threads '
            '(id, title, cwd, source, updated_at, archived)',
        )
        connection.execute(
            'INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)',
            ('one', 'Initial name', str(tmp_path), 'cli', 1, 0),
        )
    shell = SimpleNamespace(detype=lambda: os.environ | {
        'CODEX_HOME': str(tmp_path),
    })
    original: dict[str, str] = dict(os.environ)
    line: str = 'ai.resume --repo ' + str(tmp_path) + ' -b cx '
    with patch.object(XSH, 'env', shell):
        item: Any
        assert {item.display for item in completions(line)} == {
            'Initial name',
        }
        with sqlite3.connect(database) as connection:
            connection.execute(
                'UPDATE threads SET title=?', ('Renamed dialog',),
            )
        assert {item.display for item in completions(line)} == {
            'Renamed dialog',
        }
    assert dict(os.environ) == original

    with sqlite3.connect(database) as connection:
        connection.executemany(
            'INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)',
            [
                ('old', 'Alpha old', str(tmp_path), 'cli', 0, 0),
                ('new', 'Zulu recent', str(tmp_path), 'cli', 2, 0),
            ],
        )
    source: Path = (
        Path(__file__).resolve().parents[1] / 'aliases.xsh'
    )
    setup: str
    for setup in (
        'xontrib load aiskillz',
        # An already imported package must not redirect source-mode
        # completion to an older editable installation.
        'import aiskillz\n'
        'aiskillz.dialogs.list_dialogs = None\n'
        'source @(' + repr(str(source)) + ')',
    ):
        script: str = (
            setup + '\n'
            'import json\n'
            'from xonsh.completer import Completer\n'
            'from xonsh.shells.ptk_shell.completer '
            'import PromptToolkitCompleter\n'
            'from prompt_toolkit.document import Document\n'
            'from prompt_toolkit.completion import CompleteEvent\n'
            'from types import SimpleNamespace\n'
            'from unittest.mock import patch\n'
            'line = ' + repr(line) + '\n'
            'shell = SimpleNamespace('
            'prompter=SimpleNamespace(app=SimpleNamespace('
            'layout=SimpleNamespace(current_buffer=SimpleNamespace('
            'complete_state=None)))))\n'
            'completer = PromptToolkitCompleter('
            'Completer(), {}, shell)\n'
            'document = Document(line, len(line))\n'
            'orders = []\n'
            'for sort_by in ("last-update-time", "name"):\n'
            '    $AI_RESUME_COMPLETION_SORT = sort_by\n'
            '    with patch.object(completer, "reserve_space"):\n'
            '        results = list(completer.get_completions('
            'document, CompleteEvent(completion_requested=True)))\n'
            '    orders.append([item.display_text '
            'for item in results])\n'
            'print(json.dumps(orders))'
        )
        output = subprocess.run(
            [
                sys.executable,
                '-m',
                'xonsh',
                '--no-rc',
                '-c',
                script,
            ],
            cwd=tmp_path,
            env=os.environ | {
                'CODEX_HOME': str(tmp_path),
                'PYTHONPATH': str(source.parent),
            },
            check=False,
            text=True,
            capture_output=True,
        )
        assert output.returncode == 0, output.stdout + output.stderr
        assert json.loads(output.stdout) == [
            ['Zulu recent', 'Renamed dialog', 'Alpha old'],
            ['Alpha old', 'Renamed dialog', 'Zulu recent'],
        ]


def test_completer_lifecycle_and_errors() -> None:
    '''
    Reload/unload must preserve prior completers and user overrides.

    Install through the actual Xontrib twice with an existing
    registry entry, then require its restoration on unload. A user
    replacement made later must survive unregistering. Store errors
    during Tab must return no candidates instead of raising.

    '''
    from xonsh.completer import Completer

    original_ordering: Any = Completer.complete_from_context

    def prior(context: Any) -> None:
        '''
        Represent an existing user completer.

        '''
        return None

    xsh: SimpleNamespace = SimpleNamespace(
        aliases={},
        ctx={},
        completers=OrderedDict([
            ('aiskillz_resume', prior),
            ('fallback', prior),
        ]),
    )
    _load_xontrib_(xsh)
    _load_xontrib_(xsh)
    assert next(iter(xsh.completers)) == 'aiskillz_resume'
    _unload_xontrib_(xsh)
    assert Completer.complete_from_context is original_ordering
    assert xsh.completers['aiskillz_resume'] is prior
    assert xsh.ctx == {}
    register_resume_completer(xsh)

    def replacement(context: Any) -> set:
        '''
        Represent a new completer installed by the user after load.

        '''
        return set()

    xsh.completers['aiskillz_resume'] = replacement
    unregister_resume_completer(xsh)
    assert xsh.completers['aiskillz_resume'] is replacement
    with patch(
        'aiskillz._completion.dialogs.list_dialogs',
        side_effect=ValueError('Invalid store'),
    ):
        assert completions('ai.resume ') == set()
