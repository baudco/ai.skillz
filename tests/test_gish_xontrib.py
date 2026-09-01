import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'gish' / 'scripts' / 'gish-xontrib'


class GishXontribTests(unittest.TestCase):
    def fake_xonsh(
        self,
        root: Path,
        *,
        succeeds: bool = True,
    ) -> tuple[Path, Path]:
        '''
        Build an executable which records the launcher's exact argv.

        The production launcher delegates readiness and normal calls
        to an external xonsh. This fake makes the boundary observable
        without requiring modden or forge credentials in the test
        environment.

        '''
        log = root / 'argv.log'
        command = root / 'xonsh'
        root.mkdir(parents=True, exist_ok=True)
        exit_code = 0 if succeeds else 7
        command.write_text(
            '#!/usr/bin/env bash\n'
            f'printf "%s\\n" "$@" > "{log}"\n'
            f'exit {exit_code}\n'
        )
        command.chmod(0o755)
        return command, log

    def run_script(
        self,
        config_home: Path,
        *args: str,
        override: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        '''
        Run with isolated config and no inherited runtime override.

        A developer shell can export `AI_SKILLZ_GISH_XONSH`. Clearing
        it here proves tests exercise only their selected config
        path.

        '''
        env = os.environ.copy()
        env['XDG_CONFIG_HOME'] = str(config_home)
        env.pop('AI_SKILLZ_GISH_XONSH', None)
        if override is not None:
            env['AI_SKILLZ_GISH_XONSH'] = str(override)
        return subprocess.run(
            ['bash', str(SCRIPT), *args],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_configure_probes_before_persisting_runtime(self):
        '''
        Refuse a modden runtime which cannot load the gish adapter.

        Persisting an unchecked interpreter would make every
        downstream repository fail later and hide the setup error.
        The fake exits during the probe; the assertion proves no
        config is written from that failed candidate.

        '''
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            candidate, _ = self.fake_xonsh(
                root,
                succeeds=False,
            )
            result = self.run_script(
                root / 'config',
                '--configure',
                str(candidate),
            )
            config = root / 'config' / 'ai.skillz' / 'gish-xonsh'
            self.assertEqual(result.returncode, 7)
            self.assertFalse(config.exists())

    def test_configure_stores_mode_0600_absolute_path(self):
        '''
        Persist only the successfully probed absolute interpreter
        path.

        The fake records the check and exits successfully. The
        saved file must contain no shell syntax or repository state.
        Its mode must not expose the environment path to other users.

        '''
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            candidate, log = self.fake_xonsh(root)
            config_home = root / 'config'
            result = self.run_script(
                config_home,
                '--configure',
                str(candidate),
            )
            config = config_home / 'ai.skillz' / 'gish-xonsh'
            mode = stat.S_IMODE(config.stat().st_mode)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_text(), f'{candidate}\n')
            self.assertEqual(mode, 0o600)
            self.assertEqual(
                log.read_text().splitlines()[-1],
                '--adapter-check',
            )

    def test_saved_runtime_receives_exact_arguments(self):
        '''
        Forward backend arguments without shell reconstruction.

        Repository names and body paths may contain punctuation. The
        launcher passes an argv vector rather than evaluating
        a command string. The fake's line log proves each value
        survives after the fixed adapter-script prefix.

        '''
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            candidate, log = self.fake_xonsh(root)
            config_home = root / 'config'
            configured = self.run_script(
                config_home,
                '--configure',
                str(candidate),
            )
            self.assertEqual(configured.returncode, 0)
            result = self.run_script(
                config_home,
                'review-comments',
                '17',
                '--backend',
                'gitea',
            )
            forwarded = log.read_text().splitlines()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(forwarded[0], '--no-rc')
            self.assertEqual(forwarded[1], '-c')
            joined = '\n'.join(forwarded)
            self.assertIn('xontrib load gish', joined)
            adapter_index = forwarded.index('gish-adapter')
            self.assertEqual(
                forwarded[adapter_index + 1:],
                [
                    'review-comments',
                    '17',
                    '--backend',
                    'gitea',
                ],
            )

    def test_override_does_not_replace_saved_runtime(self):
        '''
        Keep a one-process runtime selection out of persistent
        config.

        A worktree can temporarily test a second modden env through
        the env var. The alternate fake must receive the check while
        the original saved interpreter remains unchanged.

        '''
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            saved, _ = self.fake_xonsh(root / 'saved')
            override, log = self.fake_xonsh(root / 'override')
            config_home = root / 'config'
            configured = self.run_script(
                config_home,
                '--configure',
                str(saved),
            )
            self.assertEqual(configured.returncode, 0)
            result = self.run_script(
                config_home,
                '--check',
                override=override,
            )
            config = config_home / 'ai.skillz' / 'gish-xonsh'
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_text(), f'{saved}\n')
            self.assertEqual(
                log.read_text().splitlines()[-1],
                '--adapter-check',
            )


if __name__ == '__main__':
    unittest.main()
