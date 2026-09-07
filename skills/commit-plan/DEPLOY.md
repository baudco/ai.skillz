# Deploying `/commit-plan`

`commit-plan` is a provider-neutral hybrid skill which composes with the
hybrid `commit-msg` and `run-tests` skills. Its `scripts/plan-exec.py` asset
executes pinned boundary specifications without duplicating commits after a
partial or complete run. The skill writes generated messages, specifications
and cached staging patches through `commit-msg`'s ignored repository-local
runtime directories and uses `run-tests` for project-check selection.

## Deployment

Deploy the dependencies first:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh run-tests <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-msg <repo> \
  --harness <claude|opencode|agents|codex|all>
bash /path/to/ai.skillz/scripts/deploy.sh commit-plan <repo> \
  --harness <claude|opencode|agents|codex|all>
```

Use the normal `init` command first for a local symlink or portable submodule
anchor. `commit-plan` stops rather than degrading when either dependency is
missing. A repository-local run-tests harness reference is optional; the
canonical `run-tests` fallback remains available when it is absent.

OpenCode skill deployment installs its dependent command shim automatically.
The explicit command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command commit-plan <repo> \
  --provider opencode
```

Invoke `$commit-plan` in Codex, `/commit-plan` in Claude Code, or
`/commit-plan` through the OpenCode command adapter. Codex uses native
skills and needs no command shim. `--harness codex` and
`--harness agents` both deploy to `.agents/skills/`; a single shared
deployment can also serve OpenCode's skill loader.

Keep `commit-plan`, `commit-msg`, and `run-tests` deployed together. A
root `AGENTS.md` supplies repository guidance; it does not install skills.
See [Shared skills across harnesses](../../docs/shared-skills.md) for local validation
and the distinction between discovery, runtime permissions, and
verified workflow execution. Other compatible harnesses use the same
shared skill bodies with their own invocation mechanism.

Plan generation resolves project commands once and materializes boundaries in
private indexes without rewriting the user's index. Targeted checks remain in
their exact-tree execution boundaries, while the broadest documented safe
regression sequence runs once against the final boundary when one exists. A
check successfully pre-executed against unchanged evidence is not rendered
twice.

The rendered command block pins one generated JSON specification by SHA-256,
runs the executor's read-only `--preflight` and `--show` modes, then invokes
`--execute <ordinal>` for each boundary. The executor recognizes an exact
completed parent/tree prefix before touching the index, checks, editor or
hooks. Repeating the complete block therefore skips committed boundaries and
resumes the first pending boundary; unexpected history stops as divergence.

`--show` plainly renders each project check, `git diff --staged` review and
`git commit --edit --file` command from the same descriptions execution uses.
At runtime the executor prints each phase, cwd and command before it runs,
reports its outcome and preserves captured stdout and stderr on failure.
Environment variable names may be shown, but their authenticated values and
the inherited environment remain hidden. Captured output escapes terminal
controls and redacts authenticated and inherited environment values.

Nothing is staged unless `--stage` is explicitly supplied. Quit and restart
OpenCode after deployment or update.
