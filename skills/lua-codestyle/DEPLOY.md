# Deploying `lua-codestyle`

Keep this whole-directory skill available for automatic selection.
Do not set `disable-model-invocation: true`; discovery must be able
to advertise it for Lua writing tasks.

Use the shared deployment workflow, not an unmanaged provider link:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink
bash /path/to/ai.skillz/scripts/deploy.sh lua-codestyle <repo> \
  --harness agents
```

Use `--method submodule` for a portable, version-pinned source anchor.
Choose another supported harness explicitly when needed. Nothing
should be staged or deployed outside the requested destination
without authorization.

Add an entry instruction to the consumer's agent guidance:

> Before writing, editing or proposing Lua code, read the selected
> `lua-codestyle` skill in full and follow its authoring and handoff
> gate, including tests and snippets. Passing tools do not replace
> inspection of actual table, argument and closure layout.

Keep the detailed policy in the skill. Reload or restart the consumer
as its harness requires after an approved source/deployment update.
This does not install a blocking checker or guarantee compliance
from an agent that never loads the instructions.
