# ai.skillz project store

`current.org` contains the intact ai.skillz scope moved from the
LNS working corpus. Task/checkbox states, carry metadata and prose
remain human-owned. `sources.toml` selects this branch's store.

Read the local `taken` skill through `.agents/skills/taken/SKILL.md`.
It requires a complete-file revision guard for each authorized save.
Use an explicitly selected source; do not write a global LNS copy.
This migration preserves a historical project scope, not a claim that
its old task descriptions or branch paths reflect current reality.

The global storespace is registered in the LNS migration worktree's
`taken/sources.toml`. Modden, Tractor and Piker include snapshots of their pre-existing
local stores. The LNS consolidation ledger pins those inputs. Before
landing, reconcile any newer edits there and retarget active agents;
do not overwrite another agent's source or infer acceptance.

Before removing this migration worktree after landing, update the
global registration and the cross-repository taken skill link to the
landed locations. The skill link intentionally points to the Taken
migration branch until that code and documentation land.

## Outstanding work

The `aiskillz-pm-20261007` subtree in `current.org` contains the
outstanding goals and next actions, with links to original notes and
unfinished plans. Keep detailed source content in its existing home.
Do not copy runtime state, prompt archives or file-inventory ledgers
into the project store. Existing acceptance states remain human-owned.

Future PM assignments start in an isolated worktree from the current
`wkt/federated_project_stores` tip. Reconcile the registered store's
newer edits before integrating this branch-local update.
