# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Backfill synthetic harness history without claiming worktree owners.

'''

from contextlib import closing, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
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
from aiskillz.cli import main
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
        with git_active=False, without altering the other harness's entry.
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
            ['git', 'init', '--quiet', str(self.repo)],
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
            'token': 'other-agent', 'provider': 'codex',
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
            'harness': harness, 'id': did, 'cwd': str(cwd),
            'name': 'Fixture dialog', 'updated_at': 0,
        })

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
            'type': 'response_item', 'payload': {
                'type': 'function_call', 'name': 'exec_command',
                'arguments': json.dumps({
                    'workdir': str(self.first), 'cmd': 'ignored',
                }),
            },
        }) + '\n{partial')
        cldlog: Path = self.cld / 'projects/project/claude-one.jsonl'
        cldlog.parent.mkdir(parents=True)
        cldlog.write_text(json.dumps({
            'sessionId': 'claude-one', 'cwd': str(self.first),
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
            'sessionId': 'cld-one', 'cwd': str(self.second),
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
            ['git', 'init', '--quiet', str(other)],
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
            'provider': 'codex', 'session': self.cx_id,
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
                'index', str(self.repo), '--no-logs',
            ]), 0)
        text: str = output.getvalue()
        self.assertIn('No new WKT relations to apply.', text)
        self.assertIn('Already recorded: 0', text)
        self.assertNotIn('Apply:', text)
        self.assertNotIn('STATUS', text)

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
            'sessionId': 'one', 'cwd': str(self.repo),
            'message': {'content': str(self.first)},
            'command': 'cd ' + str(self.first),
        }))
        output: StringIO = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                'index', str(self.repo), '--json',
            ]), 0)
        rendered: dict = json.loads(output.getvalue())
        self.assertEqual(rendered['data']['entries'], [])
        self.assertEqual(len(rendered['data']['unresolved']), 1)


if __name__ == '__main__':
    unittest.main()
