"""
EXPERIMENTAL / OPTIONAL — NOT the active `/branch-in-term` impl.
================================================================
The shipped command is the bash prompt-command in `branch-in-term.md`
(Claude runs the spawn via the Bash tool). This xonsh alias is kept
for the modden-aware WM-placement path (sibling window in the same
alacritty tree) — wire it up later if/when wanted. Use it directly
from a xonsh shell (`branch-in-term`) or via the input-box `!` form;
it is NOT invoked by the slash-command (which can't `!`-exec a
spawner).

`branch-in-term` — fork the current Claude Code session into a new
terminal, modden-workspace aware. A xonsh-alias rewrite of the
`/branch-in-term` slash-command, for when the claude session is
launched from a xonsh shell.

Load it from your xonshrc (so it's available at the prompt AND to
`xonsh -c 'branch-in-term'`, which the slash-command delegates to):

    source /path/to/ai.skillz/commands/branch-in-term/branch-in-term.xsh

Behaviour
---------
Forks via `claude --resume <id> --fork-session`:
- session id is read from `.claude/.current_session` (stashed by the
  `SessionStart` hook); falls back to `--continue` (most-recent in the
  cwd) when that file is absent.

Placement (modden-aware)
------------------------
- INSIDE a modden workspace (`$_MODDEN_RT_VARS` is exported onto every
  spawned child by `modden.runtime.term`): open the fork as a SIBLING
  window in the SAME alacritty tree via
  `alacritty msg -s <bigd_alacritty_socket> create-window` — the exact
  mechanism modden itself uses, so the WM lays it out in the workspace.
- OTHERWISE: a detached, standalone `$TERMINAL -e ...` window (inherits
  the alias' cwd so `--resume <id>` resolves in the right project).

All os-env reads go through the xonsh `Env` object (`@.env`,
i.e. `__xonsh__.env`) — never `os.environ`.
"""
import ast
import sys


def _branch_in_term(args, stdin=None):
    # `@.env` — the xonsh `Env`; ALL osenv lookups go through it.
    env = __xonsh__.env

    cwd: str = env.get('PWD') or $(pwd).strip()
    title: str = args[0] if args else 'claude:branch'

    # 1. resolve the session id: precise (hook-stashed) -> --continue
    sid: str | None = None
    sid_file = p'.claude/.current_session'
    if sid_file.exists():
        sid = sid_file.read_text().strip() or None
    resume: list = ['--resume', sid] if sid else ['--continue']
    fork_cmd: list = ['claude', *resume, '--fork-session']
    src_desc: str = f'session {sid}' if sid else 'most-recent session'

    # 2. modden-aware placement: reuse the parent workspace's alacritty
    #    IPC socket to open a sibling window in the same tree.
    sock = None
    rt_raw = env.get('_MODDEN_RT_VARS')
    if rt_raw:
        try:
            sock = ast.literal_eval(rt_raw).get('bigd_alacritty_socket')
        except (ValueError, SyntaxError) as err:
            print(
                f'branch-in-term: ignoring bad $_MODDEN_RT_VARS ({err})',
                file=sys.stderr,
            )

    if sock:
        # sibling window in the SAME modden alacritty tree (WM-placed),
        # mirroring `modden.runtime.term`'s `alacritty msg create-window`.
        ![alacritty msg -s @(sock) create-window --working-directory @(cwd) --title @(title) -e @(fork_cmd)]
        where: str = f'modden sibling window in tree @ {sock}'
    else:
        # detached standalone window; inherits this alias' cwd.
        term: str = env.get('TERMINAL') or 'alacritty'
        ![setsid -f @(term) -e @(fork_cmd)]
        where = f'new {term}'

    print(f'🌱 branch-in-term: forked {src_desc} -> {where}')


aliases['branch-in-term'] = _branch_in_term
