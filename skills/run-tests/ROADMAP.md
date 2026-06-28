# `/run-tests` — roadmap

## TODO: adopt the `/commit-msg` base + per-repo override model

Today `/run-tests` is **per-repo**: each repo generates its own
`SKILL.md` from `templates/run-tests/SKILL.md.j2` (see `DEPLOY.md` —
"there is no generic SKILL.md"); `references/tractor-example.md` is
the worked example. This duplicates the generic tractor-runtime
guidance into every consumer and has already drifted (modden's copy
is the tractor example dumped verbatim, never specialized).

Goal: unify with `/commit-msg`'s architecture —

- a **generic base** `skills/run-tests/SKILL.md` holding only the
  universally-true tractor-runtime guidance: `uv` venv detection,
  stale-registry / zombie-actor cleanup (`:1616`), the
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

`modden`'s run-tests is currently the tractor example dumped
verbatim + an inline modden fixture-hygiene note, and is **untracked
/ local-only** (so it can't propagate to the author's other test
boxes — a concrete reason to do this factor). Its per-repo
`test-harness-reference.md` should cover:

- multi-backend i3 / sway / hyprland; `--twm` / `--sw` selection
- `--headless` requirement on sway-only hosts; Xephyr via `.#i3test`
- the `--ll` / loglevel <-> tractor-plugin coupling
- venv `py313`; suite layout (`tests/test_basic_wkss.py`, ...)
- HERMETIC FIXTURES: example configs must NOT symlink into
  `~/.config/modden` — burned a full session on a phantom
  `'doggy'`->`'dev_skygpu'` runtime "swap" that was a symlinked
  fixture (fixed in modden `af043a7`).

Cross-ref: `modden:.claude/skills/run-tests/SKILL.md` carries the
inline fixture-hygiene note + a pointer back to this roadmap.
