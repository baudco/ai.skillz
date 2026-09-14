# pyskillz: preliminary harness utilities

`pyskillz` provides offline discovery of saved Codex, OpenCode, and
Claude Code dialogs. It does not start, resume, modify, or delete them.
The Python API needs only the standard library; the Xontrib requires
Xonsh in the environment loading it.

## Install and load

Install into the Python environment used by your Xonsh or application.
An editable installation follows this permanent checkout:

```xsh
import sys
uv pip install --python @(sys.executable) -e /path/to/ai.skillz
```

Start a fresh Xonsh after installing, then load the extension:

```xsh
xontrib load pyskillz
ai.dlogs
ai.dlogs --harness codex
ai.dlogs --harness oc
ai.dlogs --harness claude
ai.dlogs --harness all /path/to/repo
ai.dlogs --all
```

Editable installs register import hooks at Python startup. A shell
already running during installation may report the Xontrib missing.
Activating a virtualenv can also change subprocess lookup without
changing the Python interpreter hosting Xonsh. Check `sys.executable`
and `importlib.util.find_spec('pyskillz')` inside the failing shell
before attributing a load failure to either cause.
For immediate use in that shell, run
`source /path/to/ai.skillz/aliases.xsh`; this registers the alias
without requiring the installed package to be discoverable.

Install into the interpreter running a workspace module as well. If
that is the same virtualenv as Xonsh, one install covers both. No
package symlink into the workspace configuration directory is needed.
Use a permanent checkout for editable installs.

Add `xontrib load pyskillz` to your Xonsh setup. Installation in one
virtualenv does not install the package in other Xonsh interpreters.
The package also exports the `ai.dlogs` executable and
`python -m pyskillz`. Without installation, the original
`source /path/to/ai.skillz/aliases.xsh` entrypoint remains available.

If a development-shell hook runs `uv sync`, it can remove manually
installed packages absent from the project's dependencies. Include
this checkout explicitly when launching:

```xsh
nix develop -c uv run --with-editable /path/to/ai.skillz xonsh
```

For persistent application imports, declare `pyskillz` as an editable
local dependency in that application's project. Installing it with
`uv pip install` alone does not update the project's dependency list.

## Terminology

- **Dialog:** a persisted AI conversation with an ID. It includes
  prompts, replies, tool calls, and any stored branches, beyond the
  visible transcript alone.
- **Harness instance:** a running process interacting with a dialog.
  Resuming a dialog in a new instance does not create a new identity.
- **Session:** the upstream harness's term, used when discussing its
  storage formats or APIs. It is not our public API's umbrella term
  for both dialogs and running processes.

## Python API

```python
from pyskillz import name2id, list_dialogs

dialogs: dict[str, str] = name2id(
    path='~/repos/example', harness='codex',
)
# Every supported harness at this directory:
dialogs = name2id(path='~/repos/example', harness=None)
# Explicit subset; oc aliases opencode:
dialogs = name2id(path='~/repos/example', harness=['oc', 'claude'])
# Override both directory and harness filtering:
dialogs = name2id(all=True)
```

Harness aliases work in both the CLI and Python API: `cx` for
`codex`, `cld` for `claude`, and `oc` for `opencode`.

`path` defaults to the current directory; `~` and relative paths are
expanded. Matching uses the exact recorded cwd, with no recursive
search or Git worktree grouping. A nonexistent historical directory
can still be queried. `path=None` disables directory filtering while
retaining the selected harness. `harness` defaults to `None`: every
supported harness at the selected directory. Bare `ai.dlogs` and
`name2id()` both list all harnesses scoped to the current directory.

`all=True` selects every harness, cwd, and supported source kind,
regardless of other filter arguments. Archived Codex/OpenCode sessions
remain excluded. Normal listings exclude Codex non-interactive sources
and OpenCode child sessions; `all_sources=True` includes them. Claude
subagent logs are excluded because their IDs are not independent
interactive resume targets.

Duplicate names gain a `[harness:id]` suffix. No dialog is overwritten
because another has the same name. Exact names are retained in
`list_dialogs(...)`, which accepts the same filters and returns
records with `harness`, `id`, `name`, `cwd`, `source`, and `updated_at`
(Unix seconds). Use these records when a launcher needs to identify
which harness owns an ID. OpenCode IDs are not UUIDs.

The CLI orders columns as name, dialog ID, updated time, cwd,
worktree, then harness. `UPDATED (UTC)` shows the harness metadata
update time to the minute. Results already sort newest first using
the full `updated_at` value; displaying it does not change sorting.
Codex/OpenCode timestamps come from their stores; Claude uses log
modification time, which is a proxy for activity.
`WKT` shows the linked worktree directory name identified by Git at
the recorded cwd, including cwd values below the worktree root.
Main checkouts and unknown or deleted locations leave it blank.
This describes the saved location, not where an agent is currently
working. Table rendering queries Git once per distinct cwd; Python
and JSON discovery do not run Git. Explicit session associations in
`open-wkt` remain a follow-up.
Displayed names are capped at 36 characters, with an ellipsis for
truncation. Python and JSON retain full names.
The table abbreviates the current user's home directory as `~`;
Python and JSON retain full directory paths.
Terminal output uses grey headers. Pipes, JSON, `TERM=dumb`, and
a nonempty `NO_COLOR` environment variable disable coloring.
`--json` emits these records;
`-h` selects `--harness`; help is available through `--help`.
`-a` / `--all-repos` disables cwd filtering for the selected harness,
while `--all` corresponds to Python's `all=True`. Table output neutralizes
terminal control characters; JSON and Python retain the original names.

## Storage and limits

- Codex: read-only `CODEX_HOME/state_5.sqlite`, default `~/.codex`.
  The adapter checks required columns and supports title-only indexes.
- OpenCode: read-only `opencode.db` and `opencode-stable.db` under
  `$XDG_DATA_HOME/opencode`, default `~/.local/share/opencode`.
  `OPENCODE_DATA_DIR` is a pyskillz override. Without either DB, use
  legacy `storage/session/*/*.json` metadata. SQLite is authoritative
  when present; old JSON copies are not merged back into it.
- Claude: `$CLAUDE_CONFIG_DIR/projects`, default `~/.claude/projects`.
  Fresh `sessions-index.json` entries avoid reading corresponding logs.
  Otherwise scan top-level JSONL logs for cwd and the latest custom
  or AI title, falling back to the last-prompt metadata, summary,
  or a first-prompt excerpt. This can be
  slower than SQLite for large histories. Partial JSON lines are ignored.

Missing harness stores are skipped during multi-harness discovery.
An explicitly selected missing Codex database is reported as an error;
empty or missing Claude/OpenCode stores produce no records. Invalid
existing databases and indexes fail visibly. These are private harness
formats; future versions may require reader updates. No new persistent
cache, transcript export, server, SDK, or model credentials are needed.
Keep real session inventories outside tracked repository files.

## Verification

```xsh
python3 -B -m unittest discover -s tests -p test_dlogs.py
python3 -B -m unittest discover -s tests -p test_harness_stores.py
python3 -B -m unittest discover -s tests -p test_dialog_timestamps.py
uv build
```

## Handoff for the next package session

Keep the initial API small until it has been exercised in a workspace
module. Confirm duplicate-name labels and directory filtering with the
caller before stabilizing them as a public API. Add typed session
records when launch integration needs a stronger contract.

Qualify native SDK or ACP adapters when we need resume, live events,
interrupts, or other control operations. Preserve a distinct offline
listing path and explicit per-harness capabilities. Do not assume that
a shared model-provider API can resume another harness's dialogs.

Measure Claude log discovery on larger synthetic histories before
adding caching. If needed, use file metadata to invalidate caches and
retain a complete uncached path. Extend fixtures for storage versions,
platform-specific roots, stale indexes, and source kinds as encountered.

Before publishing, decide the package's release/version policy and
supported Python/Xonsh versions, check distribution contents, and add
package-specific CI. No publication, SDK dependency, or harness-launch
interface is part of this preliminary implementation.

## Coordination with ai.reply

The sibling `ai.reply` project already has discovery in
`python/ai_reply_codex.py`, `python/ai_reply_extract.py`, and
`lua/ai/reply/providers/claude.lua`. The intended shared boundary is
session discovery in `pyskillz`; reply extraction and picker behavior
remain consumer responsibilities. Do not import sibling checkout
files through ad hoc Python path modifications.

Before moving those callers, provide an explicit adapter for these
existing differences:

- Fields: `name` becomes `title`, `harness` becomes `provider`, and
  `cwd` becomes `directory`; `updated_at` is seconds, while the
  Python consumers use milliseconds. Claude also needs a transcript
  path, which the current shared records do not expose.
- Scope: the OpenCode consumer includes descendant directories and
  legacy worktree-owner scopes. `pyskillz` currently matches exact cwd.
- Sources: the Codex consumer selects CLI roots, while this package
  also includes editor sessions. Preserve consumer filtering.
- Titles: Claude now shares the latest custom/AI title and last-prompt
  precedence. This package additionally supports summary/first-prompt
  fallback and fresh session indexes.
- Limits: Claude's picker caps all-scope results at 30; the shared
  reader must remain complete. Apply picker limits in the consumer.

A follow-up should move representative synthetic fixtures alongside
the shared readers, test those adapters against the existing picker
contracts, and then remove duplicated discovery. SDK/control work
can proceed independently when launching or streaming is required.
