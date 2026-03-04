---
name: commit-msg
description: >
  Generate piker-style git commit messages from
  staged changes or prompt input, following the
  style guide learned from 500 repo commits.
argument-hint: "[optional-scope-or-description]"
disable-model-invocation: true
allowed-tools:
  - Bash(git *)
  - Read
  - Grep
  - Glob
  - Write
---

## Current staged changes
!`git diff --staged --stat`

## Recent commit style reference
!`git log --oneline -10`

# Piker Git Commit Message Style Guide

Learned from analyzing 500 commits from the piker
repository. If `$ARGUMENTS` is provided, use it as
scope or description context for the commit message.

## Subject Line Rules

### Length
- Target: ~50 characters (avg: 50.5 chars)
- Maximum: 67 chars (hard limit)
- Keep concise and descriptive

### Structure
- Use present tense verbs (Add, Drop, Fix, Move, etc.)
- 65.6% of commits use backticks for code references
- 33.0% use colon notation (`module.file:` prefix
  or `: ` separator)

### Opening Verbs (by frequency)
Primary verbs to use:
- **Add** (8.4%) - New features, files, functionality
- **Drop** (3.2%) - Remove features, deps, code
- **Fix** (2.2%) - Bug fixes, corrections
- **Use** (2.2%) - Switch to different approach/tool
- **Port** (2.0%) - Migrate code, adapt from elsewhere
- **Move** (2.0%) - Relocate code, refactor structure
- **Always** (1.8%) - Enforce consistent behavior
- **Factor** (1.6%) - Refactoring, code organization
- **Bump** (1.6%) - Version/dependency updates
- **Update** (1.4%) - Modify existing functionality
- **Adjust** (1.0%) - Fine-tune, tweak behavior
- **Change** (1.0%) - Modify behavior or structure

Casual/informal verbs (used occasionally):
- **Woops,** (1.4%) - Fixing mistakes
- **Lul,** (0.6%) - Humorous corrections

### Code References
Use backticks heavily for:
- **Module/package names**: `tractor`, `pikerd`,
  `polars`, `ruff`
- **Data types**: `dict`, `float`, `str`, `None`
- **Classes**: `MktPair`, `Asset`, `Position`,
  `Account`, `Flume`
- **Functions**: `dedupe()`, `push()`,
  `get_client()`, `norm_trade()`
- **File paths**: `.tsp`, `.fqme`, `brokers.toml`,
  `conf.toml`
- **CLI flags**: `--pdb`
- **Error types**: `NoData`
- **Tools**: `uv`, `uv sync`, `httpx`, `numpy`

### Colon Usage Patterns
1. **Module prefix**:
   `.ib.feed: trim bars frame to start_dt`
2. **Separator**:
   `Add support: new feature description`

### Tone
- Technical but casual (use XD, lol, .., Woops,
  Lul when appropriate)
- Direct and concise
- Question marks rare (1.4%)
- Exclamation marks rare (1.4%)

## Body Structure

### Body Frequency
- 56.0% of commits have empty bodies (one-liners
  are common)
- Use body for complex changes requiring explanation

### Bullet Lists
- Prefer `-` bullets (16.2% of commits)
- Rarely use `*` bullets (1.6%)
- Indent continuation lines appropriately

### Section Markers (in order of frequency)
Use these to organize complex commit bodies:

1. **Also,** (most common, 26 occurrences)
   - Additional changes, side effects
   - Example:
     ```
     Main change described in subject.

     Also,
     - related change 1
     - related change 2
     ```

2. **Deats,** (8 occurrences)
   - Implementation details, technical specifics

3. **Further,** (4 occurrences)
   - Additional context or future considerations

4. **Other,** (3 occurrences)
   - Miscellaneous related changes

5. **Notes,** **TODO,** (rare, 1 each)
   - Special annotations when needed

### Line Length
- Body lines: 67 character maximum
- Break longer lines appropriately

## Language Patterns

### Common Abbreviations (by frequency)
Use these freely in commit bodies:
- **msg** (29) - message
- **mod** (15) - module
- **vs** (14) - versus
- **impl** (12) - implementation
- **deps** (11) - dependencies
- **var** (6) - variable
- **ctx** (6) - context
- **bc** (5) - because
- **obvi** (4) - obviously
- **ep** (4) - endpoint
- **tn** (4) - task name
- **rn** (3) - right now
- **sig** (3) - signal/signature
- **env** (3) - environment
- **tho** (3) - though
- **fn** (2) - function
- **iface** (2) - interface
- **prolly** (2) - probably

Less common but acceptable:
- **dne**, **osenv**, **gonna**, **wtf**

### Tone Indicators
- **..** (77 occurrences) - trailing thoughts
- **XD** (17) - humor/irony
- **lol** (1) - rare, use sparingly

### Informal Patterns
- Casual contractions okay: Don't, won't
- Lowercase starts acceptable for file prefixes
- Direct, conversational tone

## Special Patterns

### Module/File Prefixes
Common in piker commits (33.0% use colons):
- `.ib.feed: description`
- `.ui._remote_ctl: description`
- `.data.tsp: description`
- `.accounting: description`

### Claude-code Footer
When written patch was assisted by claude-code, include:

```
(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

when only the commit msg was written by claude-code, use:
```
(this commit msg was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
```

## Piker-Specific Terms

### Core Components
- `pikerd` - piker daemon
- `brokerd` - broker daemon
- `tractor` - actor framework used
- `.tsp` - time series protocol/module
- `.fqme` - fully qualified market endpoint

### Data Structures
- `MktPair` - market pair
- `Asset` - asset representation
- `Position` - trading position
- `Account` - account data
- `Flume` - data stream
- `SymbologyCache` - symbol caching

### Common Functions
- `dedupe()` - deduplication
- `push()` - data pushing
- `get_client()` - client retrieval
- `norm_trade()` - trade normalization
- `open_trade_ledger()` - ledger opening
- `markup_gaps()` - gap marking
- `get_null_segs()` - null segment retrieval
- `remote_annotate()` - remote annotation

### Brokers & Integrations
- `binance` - Binance integration
- `.ib` - Interactive Brokers
- `bs_mktid` - broker-specific market ID
- `reqid` - request ID

### Configuration
- `brokers.toml` - broker configuration
- `conf.toml` - general configuration

### Development Tools
- `ruff` - Python linter
- `uv` / `uv sync` - package manager
- `--pdb` - debugger flag
- `pdbp` - debugger
- `httpx` - HTTP client
- `polars` - dataframe library
- `numpy` - numerical library
- `trio` - async framework
- `xonsh` - shell

## Examples

### Simple one-liner
```
Add `MktPair.fqme` property for symbol resolution
```

### With module prefix
```
.ib.feed: trim bars frame to `start_dt`
```

### Casual fix
```
Woops, compare against first-dt in `.ib.feed`
```

### With body using "Also,"
```
Drop `poetry` for `uv` in dev workflow

Also,
- update deps in `pyproject.toml`
- add `uv sync` to CI pipeline
- remove old `poetry.lock`
```

### With implementation details
```
Factor position tracking into `Position` dataclass

Deats,
- move calc logic from `brokerd` to `.accounting`
- add `norm_trade()` helper for broker normalization
- use `MktPair.fqme` for consistent symbol refs
```

## Output Instructions

When generating a commit message:

1. Analyze the staged diff (injected above via
   dynamic context) to understand all changes.
2. If `$ARGUMENTS` provides a scope (e.g.,
   `.ib.feed`) or description, incorporate it into
   the subject line.
3. Write the subject line following verb + backtick
   conventions above.
4. Add body only for multi-file or complex changes.
5. Write the message to a file per the instructions
   in `CLAUDE.md` (timestamp + hash filename format
   in `.claude/` subdir, plus a copy to
   `.claude/git_commit_msg_LATEST.md`).

---

**Analysis date:** 2026-01-27
**Commits analyzed:** 500 from piker repository
**Maintained by:** Tyler Goodlet
