# `/run-tests` — roadmap

## Current implementation

`run-tests` now uses the shared `skills/run-tests/SKILL.md` base plus a
repository-owned `.claude/skills/run-tests/test-harness-reference.md`.
Runtime cleanup is conditional on repository evidence; the base does not
assume a fixed `:1616` registry. The task-state marker below is preserved for
human acceptance and historical context.

## TODO: adopt the `/commit-msg` base + per-repo override model

Before the integrated deployment, `/run-tests` was **per-repo**: each repo generated its own
`SKILL.md` from `templates/run-tests/SKILL.md.j2` (see `DEPLOY.md` —
"there is no generic SKILL.md"); `references/tractor-example.md` is
the worked example. This duplicates the generic tractor-runtime
guidance into every consumer and has already drifted (modden's copy
is the tractor example dumped verbatim, never specialized).

The implemented design unified it with `/commit-msg`'s architecture:

- a **generic base** `skills/run-tests/SKILL.md` holding shared safety and
  conditional tractor-runtime guidance: `uv` venv detection,
  evidence-scoped stale-registry / zombie-actor cleanup, the
  pytest-capture-pipe hang, `tractor-reap`, last-failed JSON peek;
- which **loads a per-repo override** `test-harness-reference.md`
  from `<repo>/.claude/skills/run-tests/` for project specifics
  (venv name, test layout, change->test map, custom flags,
  known-flaky, fixture quirks) — exactly like commit-msg loads
  `style-guide-reference.md` (its base `SKILL.md` step 3).

Keep `templates/run-tests/SKILL.md.j2` for bootstrapping a repo's
override file; retire the "every repo gets a full bespoke SKILL.md"
note in `DEPLOY.md`.

### First consumer: `modden`

`modden` has **NO run-tests skill of its own**:
`modden/.claude/skills/run-tests` is a **symlink to
`~/repos/tractor/.claude/skills/run-tests`** (gitignored deploy
wiring), so modden silently reuses *tractor's* skill verbatim. There
is nowhere to put modden-specific guidance without polluting
tractor's shared skill — THAT is the concrete driver for this
factor. Its per-repo `test-harness-reference.md` should cover:

- multi-backend i3 / sway / hyprland; `--twm` / `--sw` selection
- `--headless` requirement on sway-only hosts; Xephyr via `.#i3test`
- the `--ll` / loglevel <-> tractor-plugin coupling
- venv `py313`; suite layout (`tests/test_basic_wkss.py`, ...)
- HERMETIC FIXTURES: example configs must NOT symlink into
  `~/.config/modden` — burned a full session on a phantom
  `'doggy'`->`'dev_skygpu'` runtime "swap" that was a symlinked
  fixture (fixed in modden `af043a7`).

The factor now provides a worked Modden harness example at
`references/modden-example.md`; Modden still needs to adopt a repository-owned
copy during migration. The guidance must not be added to the shared Tractor
reference (a first attempt accidentally did so and was reverted).
