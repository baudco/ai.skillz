# `/run-tests` — roadmap

## TODO: adopt the `/commit-msg` base + per-repo override model

The legacy `/run-tests` deployment is **per-repo**: each repo generates its
own full `SKILL.md` from `templates/run-tests/SKILL.md.j2` and uses the
Tractor document as its worked example. This duplicates generic runtime
guidance into every consumer and has already drifted (Modden's copy is the
Tractor skill verbatim, never specialized).

Target architecture: unify with `/commit-msg`'s model —

- a **generic base** `skills/run-tests/SKILL.md` holding only the
  cross-repo workflow: `uv` / worktree venv detection, conditional
  stale-registry and zombie-actor cleanup, pytest capture-pipe hang
  diagnosis, optional `tractor-reap`, and last-failed JSON inspection;
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

The canonical reference example records this fixture-hygiene lesson without
adding it to Tractor's local override. Consumer migration still must replace
Modden's whole-directory symlink with a canonical `SKILL.md` link and a
tracked local `test-harness-reference.md`.
