'''
Enforce editor-jumpable replies across worktrees and harnesses.

'''
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / 'skills/code-nav-refs/scripts'
)
sys.path.insert(0, str(SCRIPTS))
from code_refs import validate_response  # noqa: E402
from install_hooks import install  # noqa: E402
from stop_hook import main as stop_main  # noqa: E402


class CodeNavRefsTests(unittest.TestCase):
    '''
    Keep response roots separate from tool and editing workdirs.

    '''
    def setUp(self) -> None:
        '''
        Create two independent repository roots for citation checks.

        '''
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.reply_root = base / 'piker'
        self.other = base / 'tractor'
        for root in (self.reply_root, self.other):
            root.mkdir()
            subprocess.run(
                ['git', 'init', '-q', str(root)],
                check=True, capture_output=True,
            )
            (root / 'tests').mkdir()
        (self.reply_root / 'tests/check.py').write_text(
            'first\nsecond\n',
        )
        (self.other / 'tests/check.py').write_text(
            'first\nsecond\nthird\n',
        )

    def test_cross_worktree_citation_requires_absolute_path(
        self,
    ) -> None:
        '''
        The same relative test path exists in both repositories.

        A response about tractor could silently jump into piker
        when the assistant uses its tool workdir as the reply root.
        Strict validation rejects that ambiguity even though the
        two-line piker file exists; an absolute three-line tractor
        reference is accepted instead.

        '''
        relative = '`tests/check.py:2`'
        absolute = f'`{self.other}/tests/check.py:3`'
        self.assertEqual(
            validate_response(
                relative, self.reply_root,
                absolute_only=True,
            ),
            ['line 1: tests/check.py:2: '
             'use an absolute path for this reply'],
        )
        self.assertFalse(validate_response(
            absolute, self.reply_root,
            absolute_only=True,
        ))

    def test_lines_ranges_links_and_symlink_escape(self) -> None:
        '''
        Accept valid source lines but reject stale or escaped ones.

        Resolve file contents in both repositories and a symlink
        outside the reply root. Bad ranges, guessed line numbers,
        and link targets must fail even when their syntax parses.

        '''
        root = self.reply_root
        self.assertFalse(validate_response(
            '`tests/check.py:1-2`', root,
        ))
        self.assertFalse(validate_response(
            f'[check]({self.other}/tests/check.py:3)', root,
        ))
        spaced = self.other / 'directory with spaces'
        spaced.mkdir()
        (spaced / 'a.py').write_text('first\nsecond\n')
        self.assertFalse(validate_response(
            f'[source](<{spaced}/a.py:2>)', root,
        ))
        self.assertIn('exceeds file length', str(
            validate_response('`tests/check.py:3`', root)
        ))
        self.assertIn('reversed', str(validate_response(
            '`tests/check.py:2-1`', root,
        )))
        self.assertIn('exact', str(validate_response(
            '`tests/check.py:~2`', root,
        )))
        (root / 'tests/foreign.py').symlink_to(
            self.other / 'tests/check.py',
        )
        self.assertIn('escapes', str(validate_response(
            '`tests/foreign.py:1`', root,
        )))

    def test_fences_urls_and_unwrapped_references(self) -> None:
        '''
        Shell commands and web URLs are not local-file citations.

        Fence the command, then assert its nonexistent file and
        URL remain ignored; unwrapped prose and forge-style #L
        fragments must still receive actionable diagnostics.

        '''
        prose = (
            '```xsh\n'
            'git diff -- tests/missing.py:999\n'
            '```\n'
            '`https://example.org/file.py:42`\n'
            'Try tests/check.py:2 and `tests/check.py#L2`.\n'
        )
        problems = validate_response(prose, self.reply_root)
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any(
            'backticks' in problem for problem in problems
        ))
        self.assertTrue(any(
            'path:line' in problem for problem in problems
        ))

    def test_pinned_plan_handoff_must_be_complete(self) -> None:
        '''
        An abbreviated commit handoff may omit a planned boundary.

        Require the full rendered command artifact and overview.
        A response containing only the first executor call must
        fail, while verbatim publication of both passes.

        '''
        commands = 'plan-exec --execute 1\n\nplan-exec --execute 2\n'
        overview = '2 planned commits\n\n1. First\n2. Second\n'
        short = (
            f'{overview}\n```xsh\n'
            'plan-exec --execute 1\n```'
        )
        self.assertIn('command block', str(validate_response(
            short, self.reply_root,
            plan_commands=commands,
            plan_overview=overview,
        )))
        complete = f'{overview}\n```xsh\n{commands}```'
        self.assertFalse(validate_response(
            complete, self.reply_root,
            plan_commands=commands,
            plan_overview=overview,
        ))

    def test_stop_hook_uses_payload_root_and_blocks(self) -> None:
        '''
        Tool workdirs can belong to other repositories.

        Feed a simulated Claude/Codex Stop payload from piker
        while the validator process is not in that worktree.
        The final relative citation must be rejected and give
        the agent a concrete correction request.

        '''
        payload = {
            'cwd': str(self.reply_root),
            'last_assistant_message': '`tests/check.py:2`',
        }
        output = io.StringIO()
        with (
            patch('sys.stdin', io.StringIO(json.dumps(payload))),
            patch('sys.stdout', output),
        ):
            self.assertEqual(stop_main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['decision'], 'block')
        self.assertIn('absolute path', result['reason'])

        payload['last_assistant_message'] = (
            f'`{self.other}/tests/check.py:3`'
        )
        output = io.StringIO()
        with (
            patch('sys.stdin', io.StringIO(json.dumps(payload))),
            patch('sys.stdout', output),
        ):
            self.assertEqual(stop_main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {})

    def test_stop_hook_reports_missing_final_text(self) -> None:
        '''
        Some harness versions may omit the last assistant message.

        Without text a Stop handler cannot certify citations.
        Assert that it reports that limitation instead of claiming
        the answer passed or inventing a message from a stale log.

        '''
        output = io.StringIO()
        with (
            patch('sys.stdin', io.StringIO(json.dumps({
                'cwd': str(self.reply_root),
            }))),
            patch('sys.stdout', output),
        ):
            self.assertEqual(stop_main(), 0)
        self.assertIn(
            'not possible',
            json.loads(output.getvalue())['systemMessage'],
        )

    def test_explicit_hook_install_preserves_existing_config(
        self,
    ) -> None:
        '''
        Existing user Stop hooks must not be overwritten.

        Link only this skill into the fixture worktree. Preview
        leaves config absent; applying adds one handler alongside
        a prior handler, and a second apply is idempotent.

        '''
        root = self.reply_root
        link = root / '.agents/skills/code-nav-refs'
        link.parent.mkdir(parents=True)
        link.symlink_to(SCRIPTS.parent, target_is_directory=True)
        config = root / '.codex/hooks.json'
        config.parent.mkdir()
        original = {'hooks': {'Stop': [{
            'hooks': [{
                'type': 'command',
                'command': 'python3 existing.py',
            }],
        }]}}
        config.write_text(json.dumps(original))
        with patch('sys.stdout', io.StringIO()):
            install(root, 'codex')
        self.assertEqual(json.loads(config.read_text()), original)
        with patch('sys.stdout', io.StringIO()):
            install(root, 'codex', apply=True)
        changed = json.loads(config.read_text())
        self.assertEqual(changed['hooks']['Stop'][0], (
            original['hooks']['Stop'][0]
        ))
        self.assertEqual(len(changed['hooks']['Stop']), 2)
        with patch('sys.stdout', io.StringIO()):
            install(root, 'codex', apply=True)
        self.assertEqual(json.loads(config.read_text()), changed)

    def test_opencode_installer_is_explicitly_advisory(self) -> None:
        '''
        OpenCode has no blocking assistant-final-text plugin hook.

        Install its system-instruction plugin only on --apply,
        then refuse to overwrite an unrelated existing target.
        The preview's capability label prevents claiming the
        symlink can veto a response already displayed.

        '''
        root = self.reply_root
        anchor = root / '.ai/ai.skillz'
        anchor.parent.mkdir(parents=True)
        anchor.symlink_to(
            SCRIPTS.parents[2], target_is_directory=True,
        )
        plugin = root / '.opencode/plugins/code-nav-refs.js'
        output = io.StringIO()
        with patch('sys.stdout', output):
            install(root, 'opencode')
        self.assertFalse(plugin.exists())
        self.assertIn('instruction only', output.getvalue())
        with patch('sys.stdout', io.StringIO()):
            install(root, 'opencode', apply=True)
        self.assertTrue(plugin.is_symlink())
        self.assertTrue(plugin.resolve().is_file())
        with patch('sys.stdout', io.StringIO()):
            install(root, 'opencode', apply=True)

    def test_claude_install_keeps_other_settings(self) -> None:
        '''
        Installing one Stop handler cannot erase user configuration.

        Provide a Claude skill link and an existing settings value.
        Preview must leave the source bytes intact, while apply
        retains that value and adds only the Stop handler.

        '''
        root = self.reply_root
        link = root / '.claude/skills/code-nav-refs'
        link.parent.mkdir(parents=True)
        link.symlink_to(SCRIPTS.parent, target_is_directory=True)
        settings = root / '.claude/settings.json'
        original = {'permissions': {'deny': ['Read(secret.txt)']}}
        settings.write_text(json.dumps(original))
        with patch('sys.stdout', io.StringIO()):
            install(root, 'claude')
        self.assertEqual(json.loads(settings.read_text()), original)
        with patch('sys.stdout', io.StringIO()):
            install(root, 'claude', apply=True)
        new = json.loads(settings.read_text())
        self.assertEqual(new['permissions'], original['permissions'])
        self.assertEqual(len(new['hooks']['Stop']), 1)

    def test_installer_refuses_symlinked_user_config(self) -> None:
        '''
        A project config symlink can target unrelated user state.

        Install a valid Claude skill link, then make settings.json
        point outside the test repository. Refusing both preview
        and apply proves the installer cannot overwrite the target
        through project-local configuration indirection.

        '''
        root = self.reply_root
        link = root / '.claude/skills/code-nav-refs'
        link.parent.mkdir(parents=True)
        link.symlink_to(SCRIPTS.parent, target_is_directory=True)
        outside = self.other / 'user-settings.json'
        outside.write_text('{"user": true}')
        (root / '.claude/settings.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            install(root, 'claude', apply=True)
        self.assertEqual(outside.read_text(), '{"user": true}')

    def test_cli_rejects_wrong_worktree_and_shortened_plan(
        self,
    ) -> None:
        '''
        Validate the actual command interface used at handoff.

        A cross-worktree relative reference and a shortened
        plan must make the subprocess fail. Supplying the full
        pinned command artifact and absolute location passes.

        '''
        root = self.reply_root
        commands = root / 'commands.xsh'
        commands.write_text(
            'plan-exec --execute 1\nplan-exec --execute 2\n'
        )
        overview = root / 'overview.md'
        overview.write_text(
            '2 planned commits\n\n1. First\n2. Second\n'
        )
        argv = [
            sys.executable, str(SCRIPTS / 'code_refs.py'),
            '--reply-root', str(root), '--absolute-only',
            '--plan-commands', str(commands),
            '--plan-commands-sha256', hashlib.sha256(
                commands.read_bytes()
            ).hexdigest(),
            '--plan-overview', str(overview),
            '--plan-overview-sha256', hashlib.sha256(
                overview.read_bytes()
            ).hexdigest(),
        ]
        broken = subprocess.run(
            argv,
            input='`tests/check.py:2`\n```xsh\n'
                  'plan-exec --execute 1\n```\n',
            text=True, capture_output=True,
        )
        self.assertEqual(broken.returncode, 1)
        self.assertIn('absolute path', broken.stderr)
        self.assertIn('command block', broken.stderr)

        good = subprocess.run(
            argv,
            input=(
                overview.read_text()
                + f'`{self.other}/tests/check.py:3`\n'
                + '```xsh\nplan-exec --execute 1\n'
                + 'plan-exec --execute 2\n```\n'
            ),
            text=True, capture_output=True,
        )
        self.assertEqual(good.returncode, 0, good.stderr)
        commands.write_text('changed after pinning\n')
        changed = subprocess.run(
            argv, input='', text=True, capture_output=True,
        )
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn('digest changed', changed.stderr)


if __name__ == '__main__':
    unittest.main()
