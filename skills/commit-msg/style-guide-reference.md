# Commit Message Style Guide for `modden`

Analysis based on 200 recent commits from the `modden` repository.

## Core Principles

Write commit messages that are technically precise yet casual in
tone -- the same voice as `tractor` (same author) but grounded in
window-manager / desktop-environment domain terms. Use abbreviations
and informal language freely while keeping it crystal clear what
changed and why.

## Subject Line Format

### Length and Structure

- Target: ~50 chars (mean observed: 49.7).
- Distribution across the 200 analyzed subjects:
  * <=40 chars: 25.5%
  * 41-50 chars: 47.5%  (sweet spot)
  * 51-60 chars: 18.5%
  * 61-72 chars: 3.5%
  * >72 chars: 5.0%  (avoid; these are outliers)
- Hard-max: 67 chars (same rule as `tractor`).
- Use backticks around code elements (66% of subjects contain
  at least one backtick pair).
- Colons are rare in subjects (~5.5%), used mainly for
  file/module prefixes like `.config:` or `flake.nix:`.
- End with `?` for uncertain/experimental changes (1.5%).
- End with `!` for emphatic changes (1.0%).
- Trailing `..` to signal "there's more to the story"
  or an incomplete thought (8.5% of subjects).

### Opening Verbs (Present Tense)

Most common verbs from the 200-commit analysis:

- `Add` (14.5%) -- wholly new feature, field, TODO, test, etc.
- `Fix` (5.0%) -- bug fixes
- `Support` (3.0%) -- add compat/support for something
- `Bump` (3.0%) -- dependency / lock-file updates
- `Use` (2.5%) -- adopt new approach or API
- `Mk` (2.5%) -- make/create (abbreviated, casual)
- `Start` (2.0%) -- begin new module/feature/test
- `Rework` (2.0%) -- substantial rewrite of existing code
- `Adjust` (2.0%) -- minor tweaks
- `Mv` (1.5%) -- move/relocate (abbreviated)
- `Move` (1.5%) -- move/relocate (unabbreviated)
- `Pass` (1.5%) -- pass params through
- `Handle` (1.5%) -- add handling logic
- `Tolerate` (1.5%) -- graceful degradation
- `Skip` (1.5%) -- bypass / guard against
- `Drop` (1.5%) -- remove code/feature
- `Extend` (1.5%) -- expand existing API
- `Pin` (1.5%) -- pin a dependency version
- `Don't` (1.5%) -- disable or prevent behavior
- `Convert` (1.0%) -- transform API/data shape
- `Ensure` (1.0%) -- enforce invariant
- `Flip` (1.0%) -- toggle a default/flag
- `Tweak` (1.0%) -- small adjustment

Other observed verbs: `Swap`, `Guard`, `Wrap`, `Refactor`,
`Reformat`, `Expose`, `Implement`/`Impl`, `Port`, `Iterate`,
`Reorg`, `Break`/`Break-up`, `Factor`, `Define`, `Delegate`,
`Prevent`, `Parametrize`, `Passthru`/`Passthrough`, `Prio`,
`Suppress`, `Report`, `Enable`, `Reduce`, `Collect`, `Re-impl`,
`Split`, `Allow`, `Raise`, `Set`, `Write`, `Generalize`

Note: `Woops,` appears for self-correcting oops commits (1.0%),
and bare `WIP` / `WIP,` for work-in-progress (1.5%).

### Backtick Usage

Always backtick:
- Module paths: `.wm.i3.api`, `._better_api`, `.config._toml`,
  `.config._pymod`, `.runtime.repr`, `.progs.ssh`, `.ui.fzf`,
  `.wm.i3.layouts`, `.wm.i3.handlers`, `.wm.i3.config`,
  `.runtime.term`, `.config.wks`, `.config.dirs`
- Class / type names: `Spawn`, `Con`, `Runspace`, `Client`,
  `ProgramMngr`, `TermMngr`, `i3WmCtl`, `i3WksKey`, `GuiProg`,
  `ConfFmt`
- Function / method names with parens:
  `open_bigd()`, `get_wks_confs()`, `load_conf()`,
  `pformat_piu_tree()`, `iter_spawnables()`,
  `spawn_program()`, `open_channel_from()`,
  `.start_in_term()`, `.wait_for_win()`, `.focus()`,
  `open_from_wks()`, `open_wks_conf()`, `load_config()`,
  `select_wks()`, `maybe_get_root_sh()`,
  `dft_con_tree()`, `mk_rtree()`, `handle_kb_input()`
- Field / variable names: `bigd_win_id`, `prog_aliases`,
  `_conf_fmt`, `_flush_ignore`, `root_term_sid`,
  `con_ids`, `ssh-agent`
- Config keys / values: `'focus'`, `'shell'`, `'root'`,
  `to_output='current'`, `debug_mode`
- External tools: `sway`, `swaynag`, `swaymsg`, `fzf`,
  `trio`, `alacritty`, `ranger`, `pdbp`, `xonsh`,
  `uv2nix`, `flake.nix`, `click`, `pendulum`
- File formats: `.py`, `.toml`
- CLI flags: `--hold`, `--conf-fmt`

Most frequently backticked terms in modden subjects:
`sway` (14), `.py` (4), `bigd` (4), `fzf` (3),
`.config.load()` (3), `trio` (2), `Runspace` (2),
`pformat_piu_tree()` (2), `open_bigd()` (2),
`flake.nix` (2), `dev_modden` (2), `.config` (2),
`uv.lock` (2), `--hold` (2)

### Examples

Good subject lines:
```
Add `'focus': True,` support for a spawn(able)
Fix `sway` compat and wks-con race in `.wm.i3.api`
Mk wks-saving work on `sway` (sin crashing)
Convert `spawn_root_wks()` into `open_root_wks()` acm
Rework `.runtime.repr` to handle a `sway` DE
Support `sway` window-ID mapping in `dft_con_tree()`
Prio `.py` files in `config.get_wks_confs()`
Guard `prog_aliases` IIF there are sh-sub-cmd(s)
Open a bigd managed `ssh-agent` instance on boot
Break out TOML backend utils into `.config._toml`
Pass `shell=None` by default to `.start_in_term()`
Mv remaining `i3WmCtl` ev-meths to `.handlers`
```

## Body Format

### General Structure

- 84% of recent commits (42/50 sampled) include a body.
- Use blank line after subject.
- Max line length: 67 chars (match `tractor` convention).
- Use `-` as primary bullet (170 occurrences in 50 commits).
- Use `*` as nested sub-bullet under `-` items (103 occurrences).
- Rarely use `*` at top level (4 occurrences).
- The nested bullet pattern is:
  ```
  - top-level change description:
    * sub-detail one.
    * sub-detail two.
  ```

### Body Openers

Longer bodies frequently begin with a "clarifier" sentence
restating or expanding on the subject before diving into
bullet details. Common openers:

- `That is, ...` / `That is ...` -- rephrase what the subject
  means in concrete terms.
- `Namely ...` / `Namely,` -- specify exactly what changed.
- `Since ...` -- explain the motivation / precondition.
- `IOW, ...` -- "in other words", restate differently.
- `But only if ...` -- qualify the scope.

These appear in ~22% of bodied commits and are a strong
stylistic fingerprint.

### Section Markers

Use these markers to organize longer commit bodies:

- `Deats,` (7 occurrences) -- implementation details.
- `Impl deats,` (2) -- same but more specific.
- `Little deats,` (1) -- minor details.
- `Also,` (2 as section header) -- additional changes.
- `Lowlevel changes,` (1) -- lower-level specifics.
- `To impl,` (1) -- steps taken to implement.

The pattern is always `<Marker>,` (capitalized, trailing comma)
followed by a bullet list on the next line.

### Common Abbreviations

Use these freely (sorted by observed frequency in 50 bodies):

- `ev` (67) -- event
- `ep` (49) -- entry point
- `wks` (43) -- workspace
- `rn` (29) -- right now
- `conf` (23) -- config / configuration
- `impl` (18) -- implementation / implement
- `osenv` (17) -- OS environment variable
- `meth` (15) -- method
- `IPC` / `ipc` (21) -- inter-process communication
- `bigd` (12) -- big daemon (modden's root daemon)
- `mv` (11) -- move
- `fn` (10) -- function
- `obvi` (10) -- obviously
- `mk` (8) -- make
- `fmt` (6) -- format
- `prio` (5) -- priority / prioritize
- `orig` (5) -- original(ly)
- `deats` (4) -- details
- `mngr` (3) -- manager
- `ctx` (3) -- context
- `acm` (3) -- async context manager
- `UDS` (2) -- Unix domain socket
- `twm` (2) -- tiling window manager
- `deco` (2) -- decorator
- `IOW` (2) -- in other words
- `IIF` (1) -- if and only if
- `tgt` (1) -- target
- `rm` -- remove (used in bullet items)
- `subproc` -- subprocess
- `subl` -- sublayout
- `con` -- container (i3/sway tree node)

### Tone and Style

- Casual and conversational, same voice as `tractor`.
- Trailing `..` for open-ended / "you know what I mean" thoughts
  (57 occurrences across bodies, 17 in subjects).
- `XD` for self-deprecating humor about bugs or AI fails
  (4 in subjects).
- `Lul,` / `Woops,` to acknowledge mistakes (3 total).
- Parenthetical asides like `(sin crashing)`, `(well for whenev
  i add it)`, `(rn)`.
- Semicolons used casually mid-sentence to join related clauses.
- Contractions and informal phrasing: "Don't crash on...",
  "Yea, too many things behave oddly with...".
- Emoji: essentially never used.
- Spanish sprinkled in for fun: `sin` (without).

### Example Bodies

Simple with clarifier opener:
```
Pass `shell=None` by default to `.start_in_term()`

Such that when a spawn (config) entry doesn't set
`'shell': False` we still will use a `sh -c` injection
inside `.runtime.term._spawn_and_supervise_alacritty_subproc()`
which is generally necessary for any kind of
"non naive cmd line".
IOW, the shell is only not embedded when explicitly
`shell=False`.
```

With `Deats,` section and nested bullets:
```
Use prog-name or `Con.app_id` for win titles

Replace `Spawn.title` with first-name-in-`cmd: list[str]`
or failover to `Con.app_id` titles for now and suppress
all subwin `title_format` overrides. This was overriding
whatever built-in titling fanciness spawned program's
subwindows were using; particularly with `piker chart`
it was rekting the UX..

Deats,
- rework `.handlers.init_window_from_spawn()` title logic
  to replace `spawn.title` by,
  * using `spawn.proc._pre_embed_cmd[0]` if available,
    else `con.app_id.lower()` for `prog_title`.
  * mv title-setting logic before marking section.
- Comment out subwin title override in
  `.maybe_place_subwin()`:
  * mask out `title_format` cmd for subwindows and rm
    `title_cmd` from final ipc-cmd concatenation.
  * Keep commented alternatives for future use.
  * ALSO, add `raise_on_err=False` to final `.send_cmd()`
    to suppress crashes during subwin placement
    ipc-cmd-failures.
```

With `Also,` section:
```
Tolerate `open_from_wks()` detected spawn faults

Namely inside the `checked_spawn_entries()` closure add,
- debug-mode enabled crash handling so any
  `Spawn.maybe_raise()` call (which normally raises
  `FailedToStart`) can be `pdb`ed at fail time.
- cancel the remaining spawn in the with
  `TermMngr.cancel_all()` to retain any wks multi-prog
  interaction consistency.
- ONLY register non-crashed spawn in returned
  `spawn_entries: dict`.

Also,
- change default screen key from `'default'` to
  `'current'` in `spawn_program()`.
```

## Special Patterns

### WIP Commits
Occasional (1.5%) -- used for in-progress work that needs
a save-point. Formatted as `WIP` / `WIP,` / `WIP-workin` prefix.

### Module-Path Prefixed Subjects
Rare (~1%) but used for scoped-to-one-file changes:
```
.config: always `str`-cast the `path` section field...
.runtime.term: bump default `alacritty` font size...
flake.nix: drop `cornerboi` refs, add tip for...
```

### Merge Commits
Auto-generated, don't worry about style.

### AI-Iteration Commits
When iterating on AI-generated code (e.g. toml2py converter),
subjects track the prompt iteration:
```
First claude fail after providing input/output
After first correction prompt,
Version3 after another round of IO example..
Prompt4 tried to remove ws lines.. XD
```
These are fine for WIP history but should be squashed or
reworded before merging to main.

## Footer

The default footer credits `claude` for helping generate
the commit message content:

```
(this commit msg was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

If the patch itself was written (in whole or part) by `claude`,
use instead:

```
(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

Observed in 75% of the 50 most recent commits (reflecting
increased `claude-code` usage over time).

## Summary Checklist

Before committing, verify:
- [ ] Subject line uses present tense verb
- [ ] Subject line ~50 chars (hard max 67)
- [ ] Code elements wrapped in backticks
- [ ] Body lines <=67 chars
- [ ] Abbreviations used where natural (`wks`, `bigd`,
      `ev`, `conf`, `impl`, `obvi`, `rn`, etc.)
- [ ] Casual yet precise tone
- [ ] `-` bullets with `*` sub-bullets for details
- [ ] Section markers (`Deats,`, `Also,`) if body >3 paragraphs
- [ ] Body opener clarifies subject if non-obvious
      (`That is,`, `Namely`, `Since`, `IOW,`)
- [ ] Technical accuracy maintained
- [ ] WM/DE domain terms used correctly (`con`, `wks`,
      `bigd`, `TWM`, `DE`, `subl`, `UDS`)

## Analysis Metadata

```
Source: modden repository (913 total commits)
Commits analyzed: 200 (subjects), 50 (full bodies)
Date range: 2025-06-05 to 2026-03-13
Analysis date: 2026-03-25
```

---

(this style guide was generated by [`claude-code`][claude-code-gh]
analyzing commit history)

[claude-code-gh]: https://github.com/anthropics/claude-code
