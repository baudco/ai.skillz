# Codex adapter and validation notes

Codex uses the common deployment described in
[Shared skills across harnesses](shared-skills.md). Use
`--harness agents` or its equivalent `--harness codex` alias; both
install the same canonical skill directories at `.agents/skills/`.
The shared architecture and rollout apply to other compatible
harnesses too. This page records Codex-specific behavior and evidence.

## Discovery and invocation

Codex CLI 0.153.2 discovers symlinked skill directories but skips
symlinked `SKILL.md` files inside real directories. The shared deployer
therefore links whole directories, including the three skills that
use hybrid layouts in legacy deployments. Repository-owned runtime
state stays at its existing paths outside those source directories.

Start a fresh Codex session in the target worktree and use `/skills`
to inspect discovery. Invoke `$commit-plan`, or request the installed
`commit-plan` skill by name in a client without that picker. Slash
names elsewhere in this repository identify workflows; they are not
universal command syntax. Codex's built-in `/review` does not establish
that the installed `code-review` skill was loaded; use `$code-review`.

[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills)
describes project and user discovery, symlinks, explicit invocation,
and optional `agents/openai.yaml` metadata.

## Invocation metadata and instructions

`SKILL.md` remains the shared workflow. Existing manual-only intent
(`disable-model-invocation: true`) is mirrored in Codex's optional
`policy.allow_implicit_invocation: false` sidecar. Other skills retain
automatic invocation. Existing descriptions for `plan-io` and
`py-codestyle` describe automatic use despite manual-only frontmatter;
this change preserves their current policy. Explicit requests and
instructed dependencies can still load their bodies.

`AGENTS.md` supplies repository guidance separately from skills. It
does not translate Claude's `allowed-tools` into Codex grants. Codex
retains its own tool names, permissions, sandboxing, and model
configuration. See
[Codex repository instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Local evidence

Run `python3 tests/deploy/test-codex.py` with Codex CLI installed for
an isolated native loader check. It uses `skills/list`, starts no
model turn, and checks every manifest skill against canonical source.

Validated locally with Codex CLI 0.153.2: all 21 skills appear in its
registry. A separate `codex debug prompt-input` check loads `AGENTS.md`,
includes automatic `commit-plan`, `commit-msg`, and `run-tests`, and
excludes manual-only `pr-msg` and `py-codestyle` from automatic skill
advertising. This repository has also been self-bootstrapped and the
deployed `commit-plan` workflow used to generate a local commit plan.

This evidence does not establish successful execution of every skill
or deployment across consumer repositories. Those workflow and rollout
checks remain separate from native discovery validation.
