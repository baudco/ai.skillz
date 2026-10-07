# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Backfill synthetic harness history without claiming worktree owners.

'''

from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from aiskillz import (
    list_wkt_relations,
    list_worktree_associations,
    record_wkt_relation,
    record_worktree,
)
from aiskillz.wkt._relations import identity
from aiskillz.cli import _shell_commands, main
from aiskillz.dialogs import (
    preview_wkt_relations as preview,
    save_wkt_preview as save_preview,
    apply_wkt_preview as apply_preview,
    record_wkt_relation as record,
)
from aiskillz.wkt._lookup import WktLookup


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class DialogIndexTests(unittest.TestCase):
    '''
    Test preview/apply against isolated stores and real Git metadata.

    '''

    def test_record_wrong_harness_refuses_before_writing(
        self,
    ) -> None:
        '''
        A name under the wrong harness was saved as a literal ID.

        Return no OpenCode match for a Codex name selected via `oc`.
        The CLI must report the missing name and harness, fail, and
        leave the existing relation bytes unchanged. This includes
        the old misleading zero-write case for a bogus saved pair.

        '''
        name: str = 'config_schema_mngr'
        record(str(self.repo), 'oc', name, str(self.first))
        path: Path = (
            self.repo / '.ai/state/dialogs/relations.json'
        )
        before: bytes = path.read_bytes()
        error: StringIO = StringIO()
        with (
            patch('aiskillz.cli.dialogs.list_dialogs',
                  return_value=[]) as reader,
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            main([
                'index',
                str(self.repo),
                '--record',
                'oc',
                name,
                '--worktree',
                str(self.first),
            ])

        self.assertEqual(raised.exception.code, 1)
        self.assertIn(repr(name), error.getvalue())
        self.assertIn(
            "for harness 'oc' (opencode)\n"
            'Check --record HARNESS and the dialog name or ID\n',
            error.getvalue(),
        )
        self.assertEqual(path.read_bytes(), before)
        reader.assert_called_once_with(
            path=None, harness='opencode', all_sources=True,
            include_archived=True,
        )

    def test_record_resolves_name_to_real_id(self) -> None:
        '''
        Manual recording formerly used a saved name as the ID.

        Supply a name and an alias with metadata rooted elsewhere.
        Assert the real ID and canonical harness are persisted, then
        repeat using the ID to prove unchanged relations return zero.
        The lookup must include all directories and archive sources.

        '''
        row: dict = {
            'name': 'config_schema_mngr',
            'id': self.cx_id,
            'harness': 'codex',
            'cwd': str(self.second),
        }
        selector: str
        for selector in (row['name'], row['id']):
            output: StringIO = StringIO()
            with (
                patch('aiskillz.cli.dialogs.list_dialogs',
                      return_value=[row]) as reader,
                redirect_stdout(output),
            ):
                self.assertEqual(main([
                    'index',
                    str(self.repo),
                    '--record',
                    'cx',
                    selector,
                    '--worktree',
                    str(self.first),
                ]), 0)

            reader.assert_called_once_with(
                path=None, harness='codex', all_sources=True,
                include_archived=True,
            )

        self.assertIn('WKT relations written: 0', output.getvalue())
        relations: list[dict] = list_wkt_relations(str(self.repo))
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]['id'], self.cx_id)
        self.assertEqual(relations[0]['harness'], 'codex')

    def test_record_duplicate_names_refuses(self) -> None:
        '''
        Two saved dialogs can have the same name in one harness.

        Return two distinct IDs for a name. Verify the CLI offers
        both exact IDs and fails without creating relations.json,
        rather than silently choosing one dialog or saving its name.

        '''
        rows: list[dict] = [
            {'name': 'duplicate', 'id': 'one', 'harness': 'codex'},
            {'name': 'duplicate', 'id': 'two', 'harness': 'codex'},
        ]
        error: StringIO = StringIO()
        with (
            patch('aiskillz.cli.dialogs.list_dialogs',
                  return_value=rows),
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            main([
                'index',
                str(self.repo),
                '--record',
                'cx',
                'duplicate',
                '--worktree',
                str(self.first),
            ])

        self.assertEqual(raised.exception.code, 1)
        self.assertIn(
            "for harness 'cx' (codex)\n"
            'Pass an exact ID: one, two\n',
            error.getvalue(),
        )
        self.assertFalse((
            self.repo / '.ai/state/dialogs/relations.json'
        ).exists())

    def test_record_id_precedes_colliding_name(self) -> None:
        '''
        One dialog's name can equal another dialog's opaque ID.

        Put the name match first in discovery results. Recording
        must still select the exact ID, matching ai.resume's rule,
        and leave the other dialog without a WKT relation.

        '''
        rows: list[dict] = [
            {'name': self.cx_id, 'id': 'other', 'harness': 'codex'},
            {'name': 'actual', 'id': self.cx_id, 'harness': 'codex'},
        ]
        with (
            patch('aiskillz.cli.dialogs.list_dialogs',
                  return_value=rows),
            redirect_stdout(StringIO()),
        ):
            main([
                'index',
                str(self.repo),
                '--record',
                'cx',
                self.cx_id,
                '--worktree',
                str(self.first),
            ])

        relations: list[dict] = list_wkt_relations(str(self.repo))
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]['id'], self.cx_id)

    def test_legacy_imports_match_relation_api(self) -> None:
        '''
        Existing workspace imports used the first prototype names.

        The relation API is now the documented spelling, but an
        installed client can still use the earlier function names
        while updating its imports. Identity assertions ensure both
        spellings call the same writer and reader, not divergent
        implementations.

        '''
        self.assertIs(
            list_worktree_associations, list_wkt_relations,
        )
        self.assertIs(record_worktree, record_wkt_relation)

    def test_public_relations_keep_removed(self) -> None:
        '''
        Python callers previously could not read the table's store.

        Record two harnesses sharing an opaque ID through the public
        writer, then query from a linked checkout with a harness
        alias. Removing one target must retain its historical record
        with git_active=False, without altering the other
        harness's entry.
        This proves both repo-wide visibility and identity isolation.

        '''
        self.assertEqual(record_wkt_relation(
            str(self.repo), 'cx', 'shared', str(self.first),
        ), 1)
        record_wkt_relation(
            str(self.repo), 'cld', 'shared', str(self.second),
        )
        records: list[dict] = list_wkt_relations(
            str(self.second), harness='cx', dialog_id='shared',
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['worktree'], str(self.first))
        self.assertTrue(records[0]['git_active'])
        shutil.rmtree(self.first)
        records = list_wkt_relations(str(self.repo))
        item: dict
        by_harness: dict[str, dict] = {
            item['harness']: item for item in records
        }
        self.assertFalse(by_harness['codex']['git_active'])
        self.assertTrue(by_harness['claude']['git_active'])
        self.assertEqual(list_wkt_relations(
            str(self.repo), dialog_id='unknown',
        ), [])

    def test_shared_relation_directory(self) -> None:
        '''
        Per-checkout files would split dialog/worktree associations.

        Record from one linked checkout and read from another. The
        single association file must be under the main checkout's
        .ai directory and retain its bytes on repeated recording.
        Preview files must use that same shared directory.

        '''
        record(str(self.first), 'cx', self.cx_id, str(self.first))
        directory: Path = self.repo / '.ai/state/dialogs'
        association: Path = directory / 'relations.json'
        original: bytes = association.read_bytes()
        self.assertFalse((self.first / '.ai').exists())
        self.assertEqual(record(
            str(self.second), 'cx', self.cx_id, str(self.first),
        ), 0)
        self.assertEqual(association.read_bytes(), original)
        self.assertTrue(list_wkt_relations(
            str(self.second), harness='cx',
        )[0]['git_active'])
        path: Path
        digest: str
        path, digest = save_preview(preview(str(self.second)))
        self.assertEqual(path.parent, directory / 'previews')
        self.assertEqual(
            apply_preview(str(self.repo), path, digest, []), 0,
        )

    def test_redirected_relation_directory(self) -> None:
        '''
        A symlinked .ai could redirect writes to another worktree.

        Point the main checkout's .ai at a linked checkout and try to
        record a pair. Recording must refuse the redirect and leave
        the other checkout untouched, preserving the shared location.

        '''
        (self.repo / '.ai').symlink_to(
            self.first, target_is_directory=True,
        )
        with self.assertRaisesRegex(ValueError, 'symlink'):
            record(str(self.repo), 'cx', self.cx_id, str(self.first))
        self.assertFalse((self.first / 'state').exists())

    def test_identity_errors_identify_field(self) -> None:
        '''
        A generic identity error hid which stored field was broken.

        Exercise invalid harness, non-string ID and empty ID cases
        independently. Each error must identify the offending field
        and reason so a user can repair metadata without guessing.
        Non-UUID opaque IDs remain valid.

        '''
        with self.assertRaisesRegex(ValueError, 'harness.*wrong'):
            identity({'harness': 'wrong', 'id': 'ok'})
        with self.assertRaisesRegex(ValueError, 'id:.*str.*int'):
            identity({'harness': 'codex', 'id': 123})
        with self.assertRaisesRegex(ValueError, 'id: empty'):
            identity({'harness': 'codex', 'id': ''})
        self.assertEqual(
            identity({'harness': 'opencode', 'id': 'ses_one'}),
            ('opencode', 'ses_one'),
        )

    def setUp(self) -> None:
        '''
        Seed a repository and harness roots below one temporary dir.

        '''
        self.temp: tempfile.TemporaryDirectory = (
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(self.temp.cleanup)
        self.base: Path = Path(self.temp.name)
        self.repo: Path = self.base / 'repo'
        subprocess.run(
            [
                'git',
                'init',
                '--quiet',
                str(self.repo),
            ],
            capture_output=True, check=True,
        )
        self.common: Path = self.repo / '.git'
        self.cx: Path = self.base / 'codex'
        self.cld: Path = self.base / 'claude'
        self.oc: Path = self.base / 'opencode'
        self.cx.mkdir()
        self.oc.mkdir()
        self.env: Any = patch.dict(os.environ, {
            'CODEX_HOME': str(self.cx),
            'CLAUDE_CONFIG_DIR': str(self.cld),
            'OPENCODE_DATA_DIR': str(self.oc),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.first: Path = self.linked('first')
        self.second: Path = self.linked('second')
        self.cx_id: str = '01980000-0000-7000-8000-000000000001'
        self.dialogs: list[dict] = []
        self.reader: Any = patch(
            'aiskillz.dialogs._api.list_dialogs',
            side_effect=self.rows,
        )
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def linked(self, name: str) -> Path:
        '''
        Register a linked tree with a deliberately unrelated owner.

        '''
        root: Path = self.base / name
        root.mkdir()
        admin: Path = self.common / 'worktrees' / name
        admin.mkdir(parents=True)
        (admin / 'HEAD').write_text('ref: refs/heads/fixture\n')
        (admin / 'commondir').write_text('../..\n')
        gitfile: Path = root / '.git'
        (admin / 'gitdir').write_text(str(gitfile) + '\n')
        gitfile.write_text(f'gitdir: {admin}\n')
        (admin / 'ai-skillz-wkt').mkdir()
        (admin / 'ai-skillz-wkt/owner.json').write_text(json.dumps({
            'token': 'other-agent',
            'provider': 'codex',
            'session': 'not-a-dialog-id',
        }))
        return root

    def rows(self, path: object, harness: str) -> list[dict]:
        '''
        Return only this test's active dialogs for each harness.

        '''
        r: dict
        return [r for r in self.dialogs if r['harness'] == harness]

    def add(self, harness: str, did: str, cwd: Path) -> None:
        '''
        Add a saved dialog without changing the actual harness DBs.

        '''
        self.dialogs.append({
            'harness': harness,
            'id': did,
            'cwd': str(cwd),
            'name': 'Fixture dialog',
            'updated_at': 0,
        })

    def test_nested_repositories_are_not_wkt_evidence(self) -> None:
        '''
        Path containment used to assign nested clones to outer WKTs.

        Place independent Git repositories inside a linked checkout,
        including one with a .git file like a submodule. Their saved
        cwd and structured-history paths must not create relations
        or unresolved rows in the outer repository. An ordinary
        subdirectory must still identify its enclosing worktree.

        '''
        kind: str
        for kind in ('clone', 'gitfile'):
            nested: Path = self.first / kind
            argv: list[str] = [
                'git',
                'init',
                '--quiet',
            ]
            if kind == 'gitfile':
                argv.extend([
                    '--separate-git-dir',
                    str(self.base / 'admin'),
                ])
            subprocess.run(
                [
                    *argv,
                    str(nested),
                ], check=True,
                capture_output=True,
            )
            self.add('claude', kind, nested)

        self.add('claude', 'main-dialog', self.repo)
        log: Path = (
            self.cld / 'projects/project/main-dialog.jsonl'
        )
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({
            'sessionId': 'main-dialog',
            'cwd': str(self.first / 'gitfile'),
        }))
        plain: Path = self.second / 'src'
        plain.mkdir()
        self.add('claude', 'worktree-dialog', plain)
        plan: dict = preview(str(self.repo))
        row: dict
        self.assertEqual(
            [row['id'] for row in plan['entries']],
            ['worktree-dialog'],
        )
        self.assertEqual(
            [row['id'] for row in plan['unresolved']],
            ['main-dialog'],
        )
        self.assertEqual(
            plan['entries'][0]['candidates'][0]['worktree'],
            str(self.second),
        )

    def test_record_archived_dialogs_from_real_stores(self) -> None:
        '''
        all_sources previously left archive filters enabled.

        Seed archived Codex and OpenCode SQLite rows, then record
        each by name and by ID through the CLI and real readers.
        Relations must contain the resolved IDs; ordinary discovery
        must still hide the archived rows. This verifies manual
        recording independently of the source-kind filter.

        '''
        from aiskillz import list_dialogs

        con: sqlite3.Connection
        with closing(sqlite3.connect(
            self.cx / 'state_5.sqlite',
        )) as con:
            con.execute(
                'CREATE TABLE threads '
                '(id, title, cwd, source, updated_at, archived)',
            )
            con.execute(
                'INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)',
                ('old-cx', 'Old CX', str(self.repo), 'cli', 1, 1),
            )
            con.commit()

        with closing(sqlite3.connect(
            self.oc / 'opencode.db',
        )) as con:
            con.execute(
                'CREATE TABLE session (id, title, directory, '
                'parent_id, time_updated, time_archived)',
            )
            con.execute(
                'INSERT INTO session VALUES (?, ?, ?, ?, ?, ?)',
                ('old-oc', 'Old OC', str(self.repo), None, 1, 2),
            )
            con.commit()

        harness: str
        did: str
        name: str
        for (
            harness,
            did,
            name,
        ) in (
            ('codex', 'old-cx', 'Old CX'),
            ('opencode', 'old-oc', 'Old OC'),
        ):
            self.assertEqual(list_dialogs(
                path=None, harness=harness, all_sources=True,
            ), [])
            with patch(
                'aiskillz.cli.dialogs.list_dialogs',
                side_effect=list_dialogs,
            ):
                selector: str
                for selector in (name, did):
                    with redirect_stdout(StringIO()):
                        self.assertEqual(main([
                            'index',
                            str(self.repo),
                            '--record',
                            harness,
                            selector,
                            '--worktree',
                            str(self.first),
                        ]), 0)

        saved: dict = json.loads((
            self.repo / '.ai/state/dialogs/relations.json'
        ).read_text())
        row: dict
        self.assertEqual(
            {row['id'] for row in saved['records']},
            {'old-cx', 'old-oc'},
        )

    def test_non_string_tool_names_do_not_abort_preview(
        self,
    ) -> None:
        '''
        Null or scalar tool names used to crash history indexing.

        Write malformed function calls before a valid namespaced
        Codex tool call in the selected dialog's real JSONL log.
        Invalid names must contribute no argument-path evidence;
        `preview` must still recover the later valid call's WKT.
        Exercise both top-level calls and nested response payloads,
        checking that neither the log nor relations are modified.

        '''
        self.add('codex', self.cx_id, self.repo)
        log: Path = self.cx / 'sessions' / (
            'rollout-' + self.cx_id + '.jsonl'
        )
        log.parent.mkdir()
        nested: bool
        for nested in (False, True):
            with self.subTest(nested=nested):
                events: list[dict] = []
                name: object
                for name in (None, 42, False, [], {}):
                    call: dict = {
                        'type': 'function_call',
                        'name': name,
                        'arguments': json.dumps({
                            'workdir': str(self.second),
                        }),
                    }
                    events.append(
                        {
                            'type': 'response_item',
                            'payload': call,
                        }
                        if nested else call
                    )

                events.append({
                    'type': 'function_call',
                    'name': 'functions.exec_command',
                    'arguments': json.dumps({
                        'workdir': str(self.first),
                    }),
                })
                event: dict
                log.write_text('\n'.join(
                    json.dumps(event) for event in events
                ))
                before: bytes = log.read_bytes()
                plan: dict = preview(str(self.repo))
                self.assertEqual(plan['warnings'], [])
                self.assertEqual(len(plan['entries']), 1)
                self.assertEqual(
                    plan['entries'][0]['status'], 'ready',
                )
                self.assertEqual(
                    plan['entries'][0]['candidates'][0]['worktree'],
                    str(self.first),
                )
                self.assertEqual(log.read_bytes(), before)
                self.assertFalse((
                    self.repo / '.ai/state/dialogs/relations.json'
                ).exists())

    def test_cross_harness_structured_history(self) -> None:
        '''
        Saved main cwd hides later worktree use across harnesses.

        Seed Codex tool-workdir, Claude cwd and OpenCode
        message path.cwd. Preview must recover candidates without
        writing assignments; apply must preserve ownership and log
        bytes intact. Repeating the preview must find no new entries.

        '''
        self.add('codex', self.cx_id, self.repo)
        self.add('claude', 'claude-one', self.repo)
        self.add('opencode', 'ses_one', self.repo)
        cxlog: Path = self.cx / 'sessions' / (
            'rollout-' + self.cx_id + '.jsonl'
        )
        cxlog.parent.mkdir()
        cxlog.write_text(json.dumps({
            'type': 'response_item',
            'payload': {
                'type': 'function_call',
                'name': 'exec_command',
                'arguments': json.dumps({
                    'workdir': str(self.first),
                    'cmd': 'ignored',
                }),
            },
        }) + '\n{partial')
        cldlog: Path = self.cld / 'projects/project/claude-one.jsonl'
        cldlog.parent.mkdir(parents=True)
        cldlog.write_text(json.dumps({
            'sessionId': 'claude-one',
            'cwd': str(self.first),
        }))
        db: Path = self.oc / 'opencode.db'
        con: sqlite3.Connection
        with closing(sqlite3.connect(db)) as con:
            con.execute('CREATE TABLE message(session_id, data)')
            con.execute('INSERT INTO message VALUES (?, ?)', (
                'ses_one', json.dumps({'path': {
                    'cwd': str(self.first),
                }}),
            ))
            con.commit()

        owner: Path = (
            self.common / 'worktrees/first/ai-skillz-wkt/owner.json'
        )
        before: list[bytes] = [
            owner.read_bytes(), cxlog.read_bytes(), db.read_bytes(),
        ]
        plan: dict = preview(str(self.repo))
        self.assertEqual(len(plan['entries']), 3)
        self.assertEqual(plan['warnings'], [])
        path: Path
        digest: str
        path, digest = save_preview(plan)
        self.assertFalse((
            self.repo / '.ai/state/dialogs/relations.json'
        ).exists())
        self.assertEqual(
            apply_preview(str(self.repo), path, digest, []), 3,
        )
        self.assertEqual(
            apply_preview(str(self.repo), path, digest, []), 0,
        )
        self.assertEqual(preview(str(self.repo))['entries'], [])
        self.assertEqual(before, [
            owner.read_bytes(), cxlog.read_bytes(), db.read_bytes(),
        ])
        self.assertEqual(
            WktLookup().roots(
                str(self.repo), 'codex', self.cx_id,
            ), {str(self.first)},
        )

    def test_ambiguity_requires_choice(self) -> None:
        '''
        History can connect one dialog to several worktrees.

        Give a saved cwd and a different structured cwd; applying
        without a choice must write nothing. Choosing an enumerated
        candidate succeeds, while an unrelated target is refused.

        '''
        self.add('claude', 'cld-one', self.first)
        log: Path = self.cld / 'projects/project/cld-one.jsonl'
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({
            'sessionId': 'cld-one',
            'cwd': str(self.second),
        }))
        plan: dict = preview(str(self.repo))
        self.assertEqual(plan['entries'][0]['status'], 'ambiguous')
        path: Path
        digest: str
        path, digest = save_preview(plan)
        self.assertEqual(
            apply_preview(str(self.repo), path, digest, []), 0,
        )
        with self.assertRaisesRegex(ValueError, 'not a preview'):
            apply_preview(str(self.repo), path, digest, [
                'cld:cld-one=' + str(self.repo),
            ])
        self.assertEqual(apply_preview(
            str(self.repo), path, digest,
            ['cld:cld-one=' + str(self.second)],
        ), 1)

    def test_malformed_preview_has_cli_error_without_writes(
        self,
    ) -> None:
        '''
        A valid digest authenticates bytes, not preview entry shape.

        The CLI used to call identity() on a JSON string and leak an
        AttributeError traceback. Hash malformed entry/candidate
        shapes correctly, including a good entry before a bad one.
        Apply must produce its normal ValueError diagnostic before
        publishing a relation or creating a persistent writer guard.

        '''
        self.add('claude', 'one', self.first)
        plan: dict = preview(str(self.repo))
        good: dict = plan['entries'][0]
        malformed: object
        for malformed in (
            None,
            'bad',
            [None],
            ['bad'],
            [good, 'bad'],
            [{**good, 'candidates': None}],
            [{**good, 'candidates': ['bad']}],
            [{**good, 'candidates': [{}]}],
            [{**good, 'candidates': [{
                'worktree': [],
                'git_dir': 'not-a-path',
            }]}],
        ):
            with self.subTest(entries=malformed):
                data: dict = {**plan, 'entries': malformed}
                raw: bytes = json.dumps(data).encode()
                path: Path = self.base / 'malformed-preview.json'
                path.write_bytes(raw)
                digest: str = sha256(raw).hexdigest()
                stderr: StringIO = StringIO()
                with redirect_stderr(stderr):
                    error: Any
                    with self.assertRaises(SystemExit) as error:
                        main([
                            'index',
                            str(self.repo),
                            '--apply',
                            str(path),
                            '--sha256',
                            digest,
                        ])
                self.assertEqual(error.exception.code, 1)
                self.assertIn('Invalid preview', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
                self.assertEqual(
                    list_wkt_relations(str(self.repo)), [],
                )
                self.assertFalse((
                    self.repo / '.ai/state/dialogs/write.guard'
                ).exists())

    def test_empty_apply_checks_relation_digest(self) -> None:
        '''
        Applying no selected relations used to accept stale previews.

        Exercise both an empty preview and an ambiguous dialog with
        no choice. Each initially returns zero. Record another dialog
        after saving the preview, then require stale apply to fail
        without changing `relations.json` or leaving `write.guard`.
        This covers the CLI's no-choice path through `apply_preview`.

        '''
        ambiguous: bool
        for ambiguous in (False, True):
            with self.subTest(ambiguous=ambiguous):
                if ambiguous:
                    self.add('claude', 'cld-one', self.first)
                    log: Path = (
                        self.cld / 'projects/project/cld-one.jsonl'
                    )
                    log.parent.mkdir(parents=True)
                    log.write_text(json.dumps({
                        'sessionId': 'cld-one',
                        'cwd': str(self.second),
                    }))

                plan: dict = preview(str(self.repo))
                if ambiguous:
                    self.assertEqual(
                        plan['entries'][0]['status'], 'ambiguous',
                    )
                else:
                    self.assertEqual(plan['entries'], [])
                path: Path
                digest: str
                path, digest = save_preview(plan)
                self.assertEqual(
                    apply_preview(str(self.repo), path, digest, []),
                    0,
                )
                record(
                    str(self.repo), 'cx', 'other-' + str(ambiguous),
                    str(self.second),
                )
                directory: Path = self.repo / '.ai/state/dialogs'
                relations: Path = directory / 'relations.json'
                before: bytes = relations.read_bytes()
                with self.assertRaisesRegex(
                    ValueError, 'preview again',
                ):
                    apply_preview(str(self.repo), path, digest, [])
                self.assertEqual(relations.read_bytes(), before)
                self.assertFalse(
                    (directory / 'write.guard').exists(),
                )

    def test_digest_stale_store_and_removed_target(self) -> None:
        '''
        A reviewed proposal must not overwrite later assignments.

        Tamper with its digest, then add another confirmed dialog and
        verify stale apply leaves that store byte-identical. A fresh
        proposal is also rejected after its target tree disappears.

        '''
        self.add('claude', 'one', self.first)
        path: Path
        digest: str
        path, digest = save_preview(preview(str(self.repo)))
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            apply_preview(str(self.repo), path, 'wrong', [])
        record(str(self.repo), 'cx', 'other', str(self.second))
        file: Path = (
            self.repo / '.ai/state/dialogs/relations.json'
        )
        before: bytes = file.read_bytes()
        with self.assertRaisesRegex(ValueError, 'preview again'):
            apply_preview(str(self.repo), path, digest, [])
        self.assertEqual(file.read_bytes(), before)
        path, digest = save_preview(preview(str(self.repo)))
        (self.first / '.git').unlink()
        self.first.rmdir()
        with self.assertRaisesRegex(ValueError, 'Worktree changed'):
            apply_preview(str(self.repo), path, digest, [])

    def test_wrong_repository_and_active_writer_guard(self) -> None:
        '''
        Pinned previews belong to one repo and cannot bypass writers.

        Apply a valid preview from another repository, then create
        the real store's writer guard. Both attempts must fail before
        publishing assignments; the existing guard remains untouched.

        '''
        self.add('claude', 'one', self.first)
        path: Path
        digest: str
        path, digest = save_preview(preview(str(self.repo)))
        other: Path = self.base / 'other-repo'
        subprocess.run(
            [
                'git',
                'init',
                '--quiet',
                str(other),
            ],
            capture_output=True, check=True,
        )
        with self.assertRaisesRegex(
            ValueError, 'repository mismatch',
        ):
            apply_preview(str(other), path, digest, [])
        guard: Path = self.repo / '.ai/state/dialogs/write.guard'
        guard.mkdir()
        with self.assertRaisesRegex(ValueError, 'locked'):
            apply_preview(str(self.repo), path, digest, [])
        self.assertTrue(guard.is_dir())
        self.assertFalse(
            (guard.parent / 'relations.json').exists(),
        )

    def test_legacy_owner_and_confirmed_precedence(self) -> None:
        '''
        Old ownership records can contain an actual saved dialog ID.

        Match both provider and ID against known dialogs, never a
        generic token. After explicit retargeting, confirmed state
        must override the legacy owner evidence and survive reindex.

        '''
        self.add('codex', self.cx_id, self.repo)
        owner: Path = (
            self.common / 'worktrees/first/ai-skillz-wkt/owner.json'
        )
        owner.write_text(json.dumps({
            'provider': 'codex',
            'session': self.cx_id,
        }))
        plan: dict = preview(str(self.repo), logs=False)
        self.assertEqual(len(plan['entries']), 1)
        self.assertEqual(plan['entries'][0]['candidates'][0][
            'evidence'
        ], ['legacy-owner-matching-dialog-id'])
        record(str(self.repo), 'cx', self.cx_id, str(self.second))
        self.assertEqual(preview(str(self.repo))['entries'], [])
        self.assertEqual(WktLookup().roots(
            str(self.repo), 'codex', self.cx_id,
        ), {str(self.second)})

    def test_empty_preview_omits_apply_command(self) -> None:
        '''
        Empty previews formerly prompted users to apply nothing.

        Run the actual CLI with no recoverable dialogs and capture
        its output. It must explain the no-op and retain counts,
        without an Apply command or an empty candidate-table header.

        '''
        output: StringIO = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                'index',
                str(self.repo),
                '--no-logs',
            ]), 0)
        text: str = output.getvalue()
        self.assertIn('No new WKT relations to apply.', text)
        self.assertIn('Already recorded: 0', text)
        self.assertNotIn('Apply (', text)
        self.assertNotIn('STATUS', text)

    def test_preview_separates_matches_and_dims_labels(self) -> None:
        '''
        Keep each dialog's WKT choices readable in terminal output.

        Plain output retains copyable labels and commands. Only TTY
        output colors labels, dialog identities and WKT paths.

        '''
        class Terminal(StringIO):
            '''
            Capture terminal-only color output.

            '''

            def isatty(self) -> bool:
                '''
                Enable the terminal color branch.

                '''
                return True

        entries: list[dict] = [
            {
                'status': 'ready',
                'harness': 'codex',
                'id': 'one',
                'name': 'first',
                'candidates': [{
                    'worktree': str(self.first),
                    'evidence': ['saved-cwd'],
                }],
            },
            {
                'status': 'ambiguous',
                'harness': 'opencode',
                'id': 'two',
                'name': "second's work",
                'candidates': [{
                    'worktree': str(self.first),
                    'evidence': ['legacy-owner-matching-dialog-id'],
                }, {
                    'worktree': str(self.second),
                    'evidence': ['legacy-owner-matching-dialog-id'],
                }],
            },
        ]
        proposal: dict = {
            'entries': entries,
            'unresolved': [],
            'confirmed': 0,
            'warnings': ['check owner metadata'],
        }
        preview_path: Path = self.repo / 'preview.json'
        plain: StringIO = StringIO()
        terminal: Terminal = Terminal()
        with (
            patch('aiskillz.cli.dialogs.preview_wkt_relations',
                  return_value=proposal),
            patch('aiskillz.cli.dialogs.save_wkt_preview',
                  return_value=(preview_path, 'abcd')),
            patch.dict(
                os.environ, {'TERM': 'xterm', 'NO_COLOR': ''},
            ),
        ):
            with patch('aiskillz.cli.sys.stdout', plain):
                self.assertEqual(main([
                    'index',
                    str(self.repo),
                ]), 0)
            with patch('aiskillz.cli.sys.stdout', terminal):
                self.assertEqual(main([
                    'index',
                    str(self.repo),
                ]), 0)

        text: str = plain.getvalue()
        self.assertIn(
            'Resume (xonsh/POSIX sh): '
            'ai.resume first -a -b codex --id one\n'
            f'  "{self.first}" [saved-cwd]\n'
            f'\nAMBIGUOUS',
            text,
        )
        self.assertIn(
            'Resume (xonsh): '
            '''ai.resume @("second's work") '''
            "-a -b opencode --id @('two')\n"
            'Resume (POSIX sh): ',
            text,
        )
        posix: str = next(
            line.split(': ', 1)[1]
            for line in text.splitlines()
            if line.startswith('Resume (POSIX sh): ')
            and 'opencode' in line
        )
        self.assertEqual(shlex.split(posix), [
            'ai.resume',
            "second's work",
            '-a',
            '-b',
            'opencode',
            '--id',
            'two',
        ])
        self.assertIn(
            f'Resume (POSIX sh): {posix}\n'
            f'  "{self.first}"\n  "{self.second}"\n'
            f'\n'
            'Unresolved: 0',
            text,
        )
        self.assertIn(
            '\n'
            '\nUnresolved: 0', text,
        )
        self.assertNotIn('legacy-owner-matching-dialog-id', text)
        apply: str = next(
            line.split(': ', 1)[1]
            for line in text.splitlines()
            if line.startswith('Apply (xonsh/POSIX sh): ')
        )
        self.assertEqual(shlex.split(apply), [
            'ai.dlogs',
            'index',
            str(self.repo),
            '--apply',
            str(preview_path),
            '--sha256',
            'abcd',
        ])
        apostrophe_path: str = str(self.repo / "preview's.json")
        shell_forms: list[tuple[str, str]] = _shell_commands(
            'Apply',
            [
                'ai.dlogs',
                'index',
                str(self.repo),
                '--apply',
                apostrophe_path,
                '--sha256',
                'abcd',
            ],
            f'ai.dlogs index @({str(self.repo)!r}) '
            f'--apply @({apostrophe_path!r}) --sha256 abcd',
        )
        self.assertEqual(
            [label for label, _ in shell_forms],
            ['Apply (xonsh):', 'Apply (POSIX sh):'],
        )
        self.assertEqual(shlex.split(shell_forms[1][1]), [
            'ai.dlogs',
            'index',
            str(self.repo),
            '--apply',
            apostrophe_path,
            '--sha256',
            'abcd',
        ])
        colored: str = terminal.getvalue()
        self.assertTrue(colored.startswith(
            '\x1b[90mSTATUS     HARNESS:DIALOG ID / NAME\x1b[0m\n'
            '\x1b[90mREADY     \x1b[0m '
            '\x1b[36m"codex:one first"\x1b[0m',
        ))
        self.assertIn('\x1b[90mAMBIGUOUS \x1b[0m', colored)
        self.assertIn(
            f'\x1b[34m"{self.first}"\x1b[0m [saved-cwd]',
            colored,
        )
        for label in (
            'Unresolved:', 'Already recorded:', 'Warning:',
            'Preview:', 'SHA-256:', 'Apply (xonsh/POSIX sh):',
            'Resume (xonsh/POSIX sh):', 'Resume (xonsh):',
            'Resume (POSIX sh):',
        ):
            self.assertIn(f'\x1b[90m{label}\x1b[0m', colored)

        self.assertNotIn('\x1b', text)

    def test_prompt_text_is_not_evidence_and_cli_dispatch(
        self,
    ) -> None:
        '''
        A mentioned worktree is not a dialog assignment.

        Put its path in user text and a shell command. Neither may
        create candidates. Invoke the actual index CLI dispatcher to
        verify preview defaults and that JSON remains parseable.

        '''
        self.add('claude', 'one', self.repo)
        log: Path = self.cld / 'projects/project/one.jsonl'
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({
            'sessionId': 'one',
            'cwd': str(self.repo),
            'message': {'content': str(self.first)},
            'command': 'cd ' + str(self.first),
        }))
        output: StringIO = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                'index',
                str(self.repo),
                '--json',
            ]), 0)
        rendered: dict = json.loads(output.getvalue())
        self.assertEqual(rendered['data']['entries'], [])
        self.assertEqual(len(rendered['data']['unresolved']), 1)


if __name__ == '__main__':
    unittest.main()
