# `pyskillz` package layout

The public package lists saved Codex, OpenCode, and Claude dialogs.
`ai.dlogs index` also helps relate those dialogs to Git worktrees.
See [the package guide](../docs/pyskillz.md#install-and-load) to
install it into the Python interpreter running Xonsh or an app.

For `ai.dlogs index`, the flow is:

1. `dialogs._readers` reads dialog metadata and `dialogs._inspect`
   reads directories recorded in harness logs.
2. `wkt.WktIndexer.suggest()` compares those directories with Git
   worktrees found by `git._discovery` and returns possible
   dialog/WKT pairs.
3. `wkt._operations.save_wkt_preview()` writes a JSON preview for
   human review. `apply_wkt_preview()` verifies that file and saves
   selected relations in `.ai/state/dialogs/relations.json`.
4. `wkt.WktLookup` reads saved relations for the `ai.dlogs` WKT
   column. `cli.format_dialog_table()` formats the rows; `_xontrib`
   adapts the same CLI to an in-process Xonsh alias.

The dependency direction is `dialogs -> wkt -> git`. The CLI calls
the dialog API and WKT lookup; neither package layer imports the
CLI. Git subprocess calls are isolated in `git._commands`, making
their replacement with a library a separate change.

A WKT relation records a dialog's use of a worktree. The
`owner.json` token controls `/open-wkt` lifecycle management and
is separate from that relation. `git_active` on a returned relation
means Git still registers its WKT, not that an agent is running.

`format_dialog_table()` returns a string; it does not print. The
CLI decides whether to color the header and writes the result.
