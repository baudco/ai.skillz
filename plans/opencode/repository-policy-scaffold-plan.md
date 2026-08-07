# OpenCode Repository Policy Scaffold

## Goal

Add an opt-in deployment policy that keeps OpenCode agents within the active
Git worktree by default, makes external access visible or impossible according
to a selected profile, and discourages broad home-directory and sibling-repo
scans.

The policy is primarily a security and scope-control feature. It must not claim
that `external_directory` permissions reduce OpenCode's internal file-watcher
CPU. Watcher tuning remains a separate, repository-specific concern.

## Constraints

1. Existing deployment behavior remains unchanged unless a policy profile is
   explicitly selected.
2. Never overwrite or reformat an existing user-owned OpenCode config.
3. Never weaken an existing deny rule or silently add an allow rule.
4. Never stage unless `--stage` is explicitly supplied, and stage only exact
   policy-owned changes.
5. Never commit.
6. Refuse symlinked policy destinations, external parents, ambiguous config
   ownership, unsupported JSON/JSONC, and partial multi-file updates.
7. Preserve unrelated staged, unstaged, and untracked work.
8. Validate generated config against the installed OpenCode version before
   applying it.
9. Do not rely on `external_directory` as a complete shell sandbox. OpenCode
   can guard structured path tools, but shell command analysis is not a hard
   kernel boundary.
10. Do not mutate `AGENTS.md`, task files, or existing checklist states.

## User Interface

Add a standalone command and an `init` convenience option:

```text
deploy.sh policy <repo> --profile standard|strict|none [--dry-run] [--stage]
deploy.sh init <repo> ... [--policy standard|strict|none]
```

Semantics:

- Omitting `--policy` from `init` preserves current behavior.
- `--policy none` is an explicit no-op during fresh initialization.
- `policy --profile standard|strict` installs or updates managed policy files.
- `policy --profile none` removes only pristine, tool-managed policy files.
  It refuses removal after user edits and never removes a containing
  directory with unrelated files.
- `--dry-run` prints exact creates, updates, removals, config validation, and
  staging effects without mutation.
- `--stage` stages only the exact policy-owned paths and generated config
  changes, preserving all pre-existing index entries.

`init --policy` must preflight the anchor and policy as one operation. If the
policy cannot be installed safely, `init` must fail before creating or
initializing the source anchor.

## Managed Layout

Install these tracked repository files:

```text
.opencode/opencode.json
.opencode/policies/repository-boundary.md
.ai/opencode-policy.json
```

Use `.opencode/opencode.json` as a policy-owned config layer. OpenCode loads
the root `opencode.json` first and the `.opencode` config later, so normal root
settings are preserved while policy-owned permission keys remain explicit.

Do not mutate root `opencode.json` or `opencode.jsonc` files. If either
`.opencode/opencode.json` or `.opencode/opencode.jsonc` already exists and is
not recognized as tool-managed, refuse with:

- the conflicting path;
- the requested profile;
- a rendered config fragment for manual reconciliation;
- a reminder that config precedence and last-match permission ordering are
  security-sensitive.

The metadata file records only deployment ownership, not secrets:

```json
{
  "schema": "ai.skillz/opencode-policy/v1",
  "profile": "standard",
  "policy_version": 1,
  "managed": {
    ".opencode/opencode.json": "<sha256>",
    ".opencode/policies/repository-boundary.md": "<sha256>"
  }
}
```

Use digests to distinguish pristine generated files from user-edited files.
An update or removal may replace a file only when its current digest matches
the recorded digest. Missing, malformed, duplicated, or mismatched metadata
is a conflict, not permission to reconstruct ownership.

## Policy Profiles

### Standard

The standard profile keeps external access interactive, hard-denies common
credential stores, and makes shell execution interactive except for a small
read-only Git allowlist:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    ".opencode/policies/repository-boundary.md"
  ],
  "permission": {
    "external_directory": {
      "*": "ask",
      "~/.ssh/**": "deny",
      "~/.gnupg/**": "deny",
      "~/.config/gh/**": "deny"
    },
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git show*": "allow",
      "git rev-parse*": "allow"
    }
  }
}
```

Keep catch-all rules first because OpenCode uses last-match-wins semantics.
Do not expand the default shell allowlist merely to reduce prompts. Additions
need an explicit security review and tests for argument-bearing commands.

### Strict

The strict profile blocks structured external-directory access entirely while
retaining the same shell approval policy:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    ".opencode/policies/repository-boundary.md"
  ],
  "permission": {
    "external_directory": "deny",
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git show*": "allow",
      "git rev-parse*": "allow"
    }
  }
}
```

Strict mode is not a complete shell sandbox. A user-approved shell command
runs with the user's host authority. Document that `--auto` is incompatible
with the profile's intent because it auto-approves `ask` decisions; explicit
`deny` still remains enforced.

### None

The none profile creates no policy. When used through the standalone command,
it removes only pristine files owned by `ai.skillz/opencode-policy/v1`.

## Boundary Instruction

The managed instruction should tell every agent:

1. Treat the active Git worktree as the default filesystem boundary.
2. Do not glob, grep, list, or recursively scan `~`, `~/repos`, sibling
   repositories, or parent directories for convenience.
3. Access an external path only when the user explicitly names it, a loaded
   trusted skill/reference requires it, or repository instructions identify
   it as a dependency.
4. Explain why the external path is needed and request the narrowest path that
   satisfies the task.
5. Prefer exact files and bounded directories over home-level patterns.
6. Treat symlinks and named references as scoped capabilities, not permission
   to inspect their parents or siblings.
7. Do not use shell indirection to bypass an `external_directory` decision.
8. Stop if a task genuinely requires access denied by the strict profile and
   ask the user to choose a narrower policy or perform the action separately.

The instruction supplements permissions; it does not claim to enforce them.

## Watcher Policy

Do not add watcher ignores to the standard or strict profiles in v1.

Reasons:

- `external_directory` controls tool access, not internal indexing;
- generated-directory names are repository-specific;
- broad defaults such as `build/**` can hide legitimate source trees;
- OpenCode and its file finder already have internal exclusions;
- the motivating profile measured only 101 sleeping watches.

Add a status-only recommendation when large, existing, ignored directories
are detected. Suggest repository-owned configuration such as:

```json
{
  "watcher": {
    "ignore": ["node_modules/**", ".venv/**", "dist/**"]
  }
}
```

Do not apply suggested ignores automatically. A future independent
`--watcher-profile` feature can be designed from measured repository data.

## Implementation

### Canonical Assets

Add versioned source assets:

```text
providers/opencode/policies/standard.json
providers/opencode/policies/strict.json
providers/opencode/policies/repository-boundary.md
```

Keep templates static and deterministic. Generate metadata digests at deploy
time. Validate the canonical JSON files during repository tests.

### Deployment Functions

Extend `scripts/deploy.sh` with functions that:

1. validate a policy profile name;
2. canonicalize the target Git worktree;
3. detect existing root and `.opencode` config files;
4. reject symlinked or external `.opencode`, `.opencode/policies`, and `.ai`
   parents using existing deployment boundary helpers;
5. inspect metadata and verify managed-file digests;
6. render all intended bytes into a temporary directory;
7. validate the rendered config before mutation;
8. print a complete dry-run action list;
9. atomically create, update, or remove managed files;
10. roll back files created during the current operation if a later write
    fails, without restoring or touching pre-existing user files;
11. stage exact generated blobs only when `--stage` is supplied.

Keep config generation out of shell string splicing. Static JSON templates can
be copied byte-for-byte; metadata may be rendered by a small Python helper or
shell only after every interpolated field has a closed enum or computed digest.

### Schema Validation

Before applying a profile:

1. verify the policy JSON parses with a strict JSON parser;
2. run the installed OpenCode in pure mode against the rendered config;
3. disable project config while validating the isolated document;
4. fail before mutation if OpenCode rejects a key or value;
5. report a clear unavailable-validation error when OpenCode is absent.

Use an isolated command equivalent to:

```text
OPENCODE_DISABLE_PROJECT_CONFIG=1
OPENCODE_PURE=1
OPENCODE_CONFIG=<rendered-policy>
opencode debug config
```

Do not validate by loading target plugins, MCP servers, or repository code.

### Status And Validation

Extend `deploy.sh status` to report:

- policy profile and schema version;
- pristine, modified, missing, conflicting, or absent state;
- config and instruction digest health;
- whether `--auto` would undermine the selected profile's ask rules;
- existing unportable `skills.paths` findings unchanged;
- watcher suggestions as informational only.

Extend `scripts/validate-deployment.sh` so a recorded policy is unhealthy when:

- metadata is tracked without all managed files;
- a managed digest differs;
- the config is invalid for the installed OpenCode;
- the config has a profile shape inconsistent with metadata;
- policy files are absolute symlinks or escape the worktree;
- runtime or secret data appears in metadata.

An absent policy remains healthy because installation is opt-in.

## Test Matrix

Extend `tests/deploy/test-deploy.sh` with isolated fixtures for:

1. init without `--policy` produces the current byte-identical layout;
2. fresh `standard` policy installation;
3. fresh `strict` policy installation;
4. explicit `none` no-op during init;
5. policy dry-run predicts exact actions and changes no bytes or index state;
6. idempotent reapplication of the same profile;
7. pristine standard-to-strict and strict-to-standard transitions;
8. pristine policy removal through `none`;
9. refusal to update or remove user-edited managed files;
10. refusal when `.opencode/opencode.json` or `.jsonc` is user-owned;
11. root `opencode.json` remains byte-identical;
12. unrelated `.opencode` agents, commands, skills, and plugins survive;
13. symlinked `.opencode`, policy directory, config, instruction, metadata,
    and parent paths refuse without mutation;
14. invalid and unsupported installed OpenCode schemas fail before mutation;
15. absent OpenCode validation fails clearly before mutation;
16. `--stage` stages only policy-owned bytes and preserves unrelated index
    entries, including staged content in the same containing directories;
17. init policy failure leaves no source anchor or partial policy files;
18. subdirectory targets resolve to the Git worktree root;
19. status detects every healthy and unhealthy policy state;
20. validation accepts policy absence and rejects malformed ownership state;
21. standard rule order remains catch-all first and secret denies last;
22. strict external access remains an explicit deny;
23. both profiles keep broad shell execution at ask;
24. policy templates contain no developer-specific absolute paths.

Use a fake `opencode` executable in most tests to make schema acceptance and
rejection deterministic. Keep one optional real-config smoke test when the
installed binary is available.

## Documentation

Update:

- `README.md` with opt-in policy examples and security limitations;
- `scripts/deploy.sh --help` with policy command/profile semantics;
- `docs/deployment-consumer-inventory.md` only when recording observed
  consumer state, never to change consumer task status;
- relevant OpenCode deployment docs with restart requirements;
- `skills/harness-perf/references/opencode.md` to distinguish permission scope
  from internal watcher behavior.

Document that repository policy files are tracked project configuration and
should receive normal code review. Do not present repository-owned config as
protection from an actively malicious repository; use a user-owned inline or
managed highest-precedence config for that threat model.

## Delivery Boundaries

Prefer three commits:

1. Add canonical policy assets and standalone policy deployment/status logic.
2. Integrate `init --policy`, exact staging, validation, and regression tests.
3. Add documentation and prompt provenance.

Keep watcher automation out of these commits.

## Acceptance Criteria

- Existing deployment commands behave identically without a policy option.
- A fresh standard or strict policy installs without touching root config.
- Existing user-owned `.opencode` config is never overwritten or reformatted.
- Dry-run is complete and mutation-free.
- Managed-file updates are digest guarded and atomic.
- Standard external access asks; strict external access denies.
- Common credential directories are denied in standard mode.
- Broad shell execution never defaults to allow in either profile.
- Generated config validates against the installed OpenCode version.
- Status and deployment validation distinguish absent, healthy, modified, and
  conflicting policy states.
- Tests prove no partial filesystem or index mutation on every refusal path.
- Documentation states that the feature controls agent access, not internal
  filesystem scanning or OS-level shell sandboxing.
