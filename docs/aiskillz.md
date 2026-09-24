# aiskillz: preliminary harness utilities

`aiskillz` provides offline discovery of saved Codex, OpenCode, and
Claude Code dialogs. `ai.resume` launches the selected harness with
a saved dialog; listing and indexing do not modify harness logs.
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
xontrib load aiskillz
ai.dlogs
ai.dlogs --harness codex
ai.dlogs --harness oc
ai.dlogs --harness claude
ai.dlogs --harness all /path/to/repo
ai.dlogs --all
ai.resume 'dialog name' --dry-run
```

Editable installs register import hooks at Python startup. A shell
already running during installation may report the Xontrib missing.
Activating a virtualenv can also change subprocess lookup without
changing the Python interpreter hosting Xonsh. Check `sys.executable`
and `importlib.util.find_spec('aiskillz')` inside the failing shell
before attributing a load failure to either cause.
For immediate use in that shell, run
`source /path/to/ai.skillz/aliases.xsh`; this registers the alias
without requiring the installed package to be discoverable.

Install into the interpreter running a workspace module as well. If
that is the same virtualenv as Xonsh, one install covers both. No
package symlink into the workspace configuration directory is needed.
Use a permanent checkout for editable installs.

Add `xontrib load aiskillz` to your Xonsh setup. Installation in one
virtualenv does not install the package in other Xonsh interpreters.
The package also exports the `ai.dlogs` executable and
`python -m aiskillz`. Without installation, the original
`source /path/to/ai.skillz/aliases.xsh` entrypoint remains available.

If a development-shell hook runs `uv sync`, it can remove manually
installed packages absent from the project's dependencies. Include
this checkout explicitly when launching:

```xsh
nix develop -c uv run --with-editable /path/to/ai.skillz xonsh
```

For persistent application imports, declare `aiskillz` as an editable
local dependency in that application's project. Installing it with
`uv pip install` alone does not update the project's dependency list.

If this environment previously installed the `pyskillz` distribution,
remove that old installation and install this checkout under its new
name in the same interpreter:

```xsh
import sys
uv pip uninstall --python @(sys.executable) pyskillz
uv pip install --python @(sys.executable) -e /path/to/ai.skillz
```

Change imports to `from aiskillz import ...`, change Xonsh setup to
`xontrib load aiskillz`, and restart Xonsh. A `uv sync`-managed app
must also replace its dependency declaration. The `ai.dlogs` and
`ai.resume` command names stay the same.

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
from aiskillz import name2id, list_dialogs

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
which harness owns an ID. `name2id()` deliberately returns only
names and IDs; do not parse duplicate-name suffixes for metadata.
Use `list_dialogs()` when launching the corresponding harness:

```python
dialogs = list_dialogs(path='~/repos/example')
for dialog in dialogs:
    print(dialog['name'], dialog['id'], dialog['harness'])
```

For an exact ID lookup across directories:

```python
from aiskillz import get_dialog

dialog = get_dialog(dialog_id)
# Optional harness filter; aliases work here too:
dialog = get_dialog(dialog_id, harness='cx')
```

`get_dialog()` returns the same metadata record or `None` when no
eligible dialog matches. If several harnesses share the ID, it raises
`ValueError` and requires a harness filter. It uses the existing
readers and source/archive filters; it does not return a transcript.
Store errors propagate rather than masquerading as a missing ID.

OpenCode IDs are not UUIDs.

The CLI orders columns as name, dialog ID, WKT, updated time,
CWD, then harness. When every displayed dialog has the same CWD
or harness, it shows that value once above the table and drops
the repeated column. `CWD` uses `~` for your home directory;
`HARNESS` uses the canonical name even when filtered with `cx`,
`oc`, or `cld`. JSON and Python records keep all fields.
`UPDATED (UTC)` shows the harness metadata
update time to the minute. Results already sort newest first using
the full `updated_at` value; displaying it does not change sorting.
Codex/OpenCode timestamps come from their stores; Claude uses log
modification time, which is a proxy for activity.
`WKT` shows a linked worktree associated with the dialog. For example,
a harness may remember that a dialog started in `/repos/demo`, while
the agent later used `/open-wkt feature` to work in
`/repos/demo/wkts/feature`. The table can show `feature` even though
the harness's saved `cwd` still says `/repos/demo`.

The column checks these sources in order:

1. A relation written to `relations.json` by `/open-wkt`,
   `ai.dlogs index --record`, or a user-reviewed `index --apply`.
2. A dialog ID recorded in an older worktree `owner.json`, when that
   dialog has no relation in `relations.json`. Several matching old
   owner files produce `(multiple)`.
3. The linked Git worktree containing the dialog's saved `cwd`.

These are records of worktree use (for example, from a prior
`/open-wkt` invocation by the agent). Only worktrees that still exist
and remain registered with Git appear in the table. A removed/deleted
saved `cwd` can prevent finding the repository at all; that row's
worktree column stays blank. The main checkout also has a blank WKT
column when no linked WKT relation is known.

During one `ai.dlogs` invocation, Git discovery and relation-file
reads are reused across rows in the same repository. The next
invocation reads them again. This is what the code's lookup cache
means; it is an in-memory dictionary lasting for one listing.

## Read WKT relations from Python

`list_wkt_relations()` reads the dialog-to-WKT relations saved in
`relations.json`. You can call it from any checkout of the repo:

```python
from aiskillz import list_dialogs, list_wkt_relations

relations: list[dict] = list_wkt_relations(
    path='~/repos/demo',
    harness='oc',  # omit to include every harness
    dialog_id='ses_example',  # omit to include every dialog
)
```

An example returned record is:

```python
relation: dict = {
    'harness': 'opencode',
    'id': 'ses_example',
    'worktree': '/repos/demo/wkts/feature',
    'git_dir': '/repos/demo/.git/worktrees/feature',
    'source': 'explicit-record',
    'git_active': True,
}
```

`git_active=True` means Git still registers this worktree and its
directory exists. It says nothing about whether an agent is running.
Removed worktrees remain in the result with `git_active=False`.
Missing `relations.json` returns `[]`; invalid JSON or an invalid
repository raises an error.
The earlier `list_worktree_associations()` import remains an alias
while callers move to `list_wkt_relations()`.

To attach a relation to a dialog record, match both `harness` and
`id`: different harnesses may use the same dialog ID string.
The `**dialog` syntax merges the original dialog dictionary into
each new dictionary:

```python
relations: list[dict] = list_wkt_relations('~/repos/demo')
relation: dict
by_dialog: dict[tuple[str, str], dict] = {
    (relation['harness'], relation['id']): relation
    for relation in relations
}
dialog: dict
dialogs: list[dict] = [
    {
        # Python's ** unpacking merges the dialog dictionary here.
        **dialog,
        'wkt_relation': by_dialog.get(
            (dialog['harness'], dialog['id']),
        ),
    }
    for dialog in list_dialogs('~/repos/demo')
]
```

Each `wkt_relation` is the matching dictionary or `None`.
`list_dialogs()` itself reads harness metadata only. The separate
relation call makes the extra Git and file reads explicit.

Displayed names are capped at 36 characters, with an ellipsis for
truncation. Python and JSON retain full names.
The table abbreviates the current user's home directory as `~`;
Python and JSON retain full directory paths.
Terminal output uses grey column headers and context keys; values
keep the terminal's normal color. Pipes, JSON, `TERM=dumb`, and
a nonempty `NO_COLOR` environment variable disable coloring.
`--json` emits these records;
`-b` (backend) selects `--harness`; `-h` and `--help` show help.
`-a` / `--all-repos` disables cwd filtering for the selected harness,
while `--all` corresponds to Python's `all=True`. Table output neutralizes
terminal control characters; JSON and Python retain the original names.

## Resume a named dialog

`ai.resume NAME` finds a dialog name in the current directory
and launches the matching harness with its dialog ID. Full names
match exactly. A copied 36-character NAME ending in `…` also works
when it identifies one dialog. The lookup reads the same saved
dialog records as `ai.dlogs`. Inspect the choice first:

```xsh
ai.resume 'xharness_w_codex' --dry-run
ai.resume 'xharness_w_codex'
```

`--dry-run` prints JSON with the selected harness, ID, launch cwd,
and exact argv without starting an instance. The installed package
provides an `ai.resume` executable and Xontrib alias; sourcing
`aliases.xsh` provides a no-install Xonsh alias too.

The default search uses the current directory, just like `ai.dlogs`.
Use `--repo PATH` for another saved cwd or `-a` / `--all-repos` to
search all saved directories. Exact duplicate names fail with a
list of harnesses, IDs, and saved directories; narrow them with
`-b` / `--harness`, `--repo`, or `--id`:

```xsh
ai.resume 'Quick availability check' -b oc
ai.resume 'shared name' -a --id ses_example
```

When one active WKT is recorded for that dialog, the harness starts
there. Otherwise it starts in the dialog's saved cwd. If several
WKTs match, or the selected directory no longer exists, use
`--cwd PATH` to choose a launch directory explicitly. The wrapper
passes an argv list directly to `codex resume ID`,
`opencode --session ID`, or `claude --resume ID`; it does not
interpret the dialog name as a shell command.

## Storage and limits

- Codex: read-only `CODEX_HOME/state_5.sqlite`, default `~/.codex`.
  The adapter checks required columns and supports title-only indexes.
- OpenCode: read-only `opencode.db` and `opencode-stable.db` under
  `$XDG_DATA_HOME/opencode`, default `~/.local/share/opencode`.
  `OPENCODE_DATA_DIR` is an aiskillz override. Without either DB, use
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

## Record WKT relations with /open-wkt

Deploy the `open-wkt` skill from this repo (the `ai.skillz`
native way). After creating or entering a worktree and checking its
owner, the agent records its dialog ID and WKT path in
`relations.json`. If the Python package or Xonsh alias is not
available yet, see [Install and load](#install-and-load) near the
top of this guide.

ID here means the harness's session ID (what `ai.skillz` calls a
**dialog ID**). Some harnesses use UUIDs; OpenCode uses `ses_...` IDs.
If no session ID can be found, the agent skips relation recording
and explains that in its reply to you. The opened worktree remains
usable. Supply the ID later with `--record`, or recover it with
`ai.dlogs index` when the logs contain enough information.

The skill calls `aiskillz.record_wkt_relation()` when Python can import
this package. Otherwise, it runs the `aiskillz/cli.py` script from
this repo's source files. Both paths use the same relation writer.

To associate a worktree to a dialog explicitly, use:

```xsh
ai.dlogs index --record oc ses_example --worktree /repos/demo/wkts/feature
```

Or from Python:

```python
from aiskillz import record_wkt_relation

changed: int = record_wkt_relation(
    repo='~/repos/demo',
    harness='oc',
    dialog_id='ses_example',
    wkt='/repos/demo/wkts/feature',
)  # 0 = unchanged, 1 = relation written
```

`--record` can replace this dialog's previously recorded WKT.
`--apply` only fills missing relations. Other dialogs' relations
remain intact. The separate `owner.json` token controls who may
manage or remove a worktree under `/open-wkt`; recording a dialog's
WKT relation does not transfer that lifecycle ownership.
The earlier `record_worktree()` import remains an alias.

## Recover WKT relations for existing dialogs

An existing dialog may have no WKT relation because its worktree
was opened before relation recording existed, or without this repo's
`/open-wkt` skill. Recovery has two steps: inspect possible
dialog/WKT pairs, then save the pairs you accept.

### 1. Inspect possible dialog/WKT pairs

From any checkout of the repository, run:

```xsh
ai.dlogs index
```

`ai.dlogs index` compares directories recorded in existing dialogs
with Git's registered worktrees. It prints possible pairs and writes
a **preview file** under `.ai/state/dialogs/previews/`. That JSON
file records the dialog IDs, matching WKT paths, the evidence for
each match, and the checksum of `relations.json` at this point.
The file pins what you review for the later `--apply` command.
For example, one printed pair might be:

```text
STATUS     HARNESS:DIALOG ID / NAME
READY      "opencode:ses_example implement_feature"
  "/repos/demo/wkts/feature" [saved-cwd]
```

`READY` means the command found one WKT for this dialog.
`AMBIGUOUS` means it found several; choose one before saving a
relation. In the preview JSON, the `candidates` field lists those
WKT paths and the evidence next to each path.

The command then prints the preview path, its SHA-256 checksum, and
an `Apply:` line. Copy that line only after reviewing the pairs. The
first command creates the preview file; the `Apply:` command saves
the selected relations in `relations.json`, which `ai.dlogs` and
`list_wkt_relations()` read.

### 2. Save the reviewed relations

For example, a printed `Apply:` line could be:

```xsh
ai.dlogs index @('/repos/demo') --apply @('/repos/demo/.ai/state/dialogs/previews/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json') --sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

That digest is illustrative; use the exact `Apply:` line printed by
your own preview. Python callers can use JSON output to keep the
actual path and digest together:

```xsh
import json
proposal = json.loads($(ai.dlogs index --json))
print(json.dumps(proposal['data'], indent=2))
# Review the printed dialog/WKT pairs before running this line.
ai.dlogs index --apply @(proposal['path']) --sha256 @(proposal['sha256'])
```

For a dialog with several proposed worktrees, add the exact path you
want to save. For example, if `ses_example` matched both `feature`
and `experiment`, choose `feature` with:

```xsh
ai.dlogs index --apply @(proposal['path']) --sha256 @(proposal['sha256']) --choose 'oc:ses_example=/repos/demo/wkts/feature'
```

The chosen WKT must be one of that dialog's paths in the preview
JSON. `--apply` checks the preview checksum and current Git WKT
registrations before saving relations. If `relations.json` changed
since the preview was generated, create and review a new preview.
Reapplying an already-saved pair changes nothing. Later `index`
runs skip dialogs already recorded in `relations.json`.

The current file format saves one worktree per dialog. Supporting
`dialog -> set[WKT]` is a planned extension, including supervisor
dialogs coordinating several worktrees. Multiple historical matches
can be valid; today's `--choose` requirement reflects the current
one-WKT-per-dialog file format.

### How the command finds possible WKT paths

- The dialog's saved `cwd` (the directory remembered by its harness).
- Older `owner.json` files (the worktree lifecycle record written by
  `/open-wkt`). A `dialog` field explicitly records harness and ID;
  an older `session` value is accepted only if it exactly matches a
  known dialog ID from the same harness.
- Codex JSONL logs (`cwd` metadata and `cwd`/`workdir` arguments sent
  to shell tools, which identify the requested command directory).
- Claude JSONL logs (`cwd` fields recorded on dialog events).
- OpenCode message rows (`path.cwd` inside the message's JSON data,
  recording the directory associated with that message).

`--no-logs` uses only saved `cwd` and old owner files. Unreadable
harness data is listed under `Warning:`. Missing logs or removed
worktrees can leave dialogs under `Unresolved`; those have no
recoverable WKT relation in this run. Existing archive/source filters
from dialog listing still apply.

## Relation files

The relation files live beneath the **main checkout's**
`.ai/state/dialogs`, even when invoked from a linked worktree:

```text
.ai/state/dialogs/
  relations.json       saved dialog/worktree pairs
  previews/<sha256>.json   proposed pairs from ai.dlogs index
  write.guard/            exists only while a writer holds the lock
    writer.json           PID of that Python writer
```

Git identifies the main checkout. A separate Git directory needs
`core.worktree` configured to identify that checkout; without it,
creating a new relation file reports an error. For a bare
repository, `.ai/state/dialogs` is beneath the bare repository
directory. All linked checkouts use the same location.

`write.guard` is acquired with an exclusive directory creation. A
crashed writer can leave it behind and block later writes. Inspect
`writer.json` and the process before removing a stale guard; PID
reuse means the number alone is insufficient to identify the writer.

An earlier local prototype wrote
`.git/ai-skillz-dialogs/associations.json`. This version does not
import that file or its saved previews. If you used that prototype,
inspect its dialog/WKT pairs and record each one with `--record`, or
review a fresh `ai.dlogs index` preview. Leave the old file intact
until you have verified the new `relations.json` records.

## Python package layers

See [the package layout](../aiskillz/README.md) for the entry points,
dependency direction, and how the CLI, dialog readers, WKT indexer,
and Git discovery work together.

## Verification

Install the `test` extra in your development environment for pytest.
The existing unittest suites run under pytest without a rewrite;
new tests can use pytest fixtures as shared setup evolves. Xontrib
integration tests also require Xonsh in that environment.

```xsh
python -m pytest tests/test_dlogs.py tests/test_harness_stores.py tests/test_dialog_timestamps.py tests/test_worktree_dialogs.py tests/test_dialog_index.py tests/test_git_discovery.py tests/test_aiskillz_layers.py
uv build
```

## Handoff for the next package session

TODO: evaluate KDL 2 for association metadata and previews. Start
with [kdl-py](https://github.com/tabatkins/kdlpy): its Python parser
and serializer support KDL 2 without requiring a native build.
Before switching formats, define the schema, deterministic encoding
for preview hashes, and regenerate previews when their format
changes. JSON remains the current on-disk format.

TODO: qualify [dulwich worktree discovery](https://dulwich.io/api/dulwich.worktree.WorkTreeContainer.html)
([source](https://github.com/dulwich/dulwich)) as the shared backend
for repository and linked-worktree queries.
Measure it against the cached Git CLI path using many dialogs in one
repo and dialogs across repos. Cover bare repositories, relocated
checkouts, stale registrations, symlinks and conflicting `GIT_*`
environment variables before replacing the current queries. `dulwich`
can remove discovery subprocesses; it cannot interpret our owner
files or decide which dialog association takes precedence.

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
session discovery in `aiskillz`; reply extraction and picker behavior
remain consumer responsibilities. Do not import sibling checkout
files through ad hoc Python path modifications.

Before moving those callers, provide an explicit adapter for these
existing differences:

- Fields: `name` becomes `title`, `harness` becomes `provider`, and
  `cwd` becomes `directory`; `updated_at` is seconds, while the
  Python consumers use milliseconds. Claude also needs a transcript
  path, which the current shared records do not expose.
- Scope: the OpenCode consumer includes descendant directories and
  legacy worktree-owner scopes. `aiskillz` currently matches exact cwd.
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
