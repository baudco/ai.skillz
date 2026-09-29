# Final-answer reference checking

`code-nav-refs` defines the formatting contract. Its script is the
mechanical checker; simply discovering the skill cannot force a model
to call it. A handler can only block delivery when the harness
actually exposes the finished assistant text and a Stop decision.

## Opt-in installation

Deploy the skill in the intended consumer worktree first. The
installer previews the change by default and preserves existing
settings and hooks. Apply only after inspecting the preview:

```xsh
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness claude
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness claude --apply
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness codex
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness codex --apply
```

The Claude handler is appended to `.claude/settings.json` under
`hooks.Stop`; the Codex handler is appended to `.codex/hooks.json`.
Both call the same `scripts/stop_hook.py`. They read the current
turn's `last_assistant_message` from the Stop payload and use its
`cwd` to discover the original reply root. If that root is absent,
absolute references can still be checked. Set
`AI_SKILLZ_REPLY_ROOT` to a verified worktree root only when the
harness's `cwd` does not identify the user's editor workspace.
Both enforce absolute path:line citations in replies to avoid
same-named relative files in another worktree.
They request another agent turn on failure; already-streamed text
may have been visible, so a Stop decision is not pre-display veto.

Project hooks require the harness's trust/activation step. Claude
and Codex must reload configuration after applying the change;
Codex additionally requires trusting the new hook via `/hooks`.
The installer refuses malformed config and conflicting targets.
It does not edit a consumer repo merely because the skill was
deployed or because its instructions were loaded.

## OpenCode limitation

OpenCode's published plugin interface exposes assistant-message
updates as events, not a blocking final-text decision. The
optional local plugin only injects the reference rule into the
system text of each model call:

```xsh
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness opencode
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/install_hooks.py . --harness opencode --apply
```

It links `.opencode/plugins/code-nav-refs.js` to the source plugin
and requires an OpenCode restart. It cannot stop an incorrect
answer that the model emits. For headless or export workflows,
validate the final captured reply as a separate command before
display/publication. Interactive OpenCode requires either an
upstream pre-display hook or a trusted response-rendering wrapper
for a hard delivery gate. Post-display `message.part.updated` or
`session.idle` events are diagnostic, not a substitute.

## One-shot check and plan handoff

Run the shared checker on a saved answer with an explicit original
reply root. It returns a nonzero status on malformed, stale or
wrong-worktree locations:

```xsh
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/code_refs.py --reply-root /absolute/original/worktree --absolute-only < /absolute/answer.md
```

For a `/commit-plan` answer, also require the exact rendered native
overview and complete commands from the pinned plan package:

```xsh
OVERVIEW_SHA256 = 'digest copied from finalize receipt'
COMMANDS_SHA256 = 'digest copied from finalize receipt'
python3 .ai/ai.skillz/skills/code-nav-refs/scripts/code_refs.py --reply-root /absolute/original/worktree --absolute-only --plan-overview /absolute/package/final/overview.md --plan-overview-sha256 @(OVERVIEW_SHA256) --plan-commands /absolute/package/final/commands.xsh --plan-commands-sha256 @(COMMANDS_SHA256) < /absolute/answer.md
```

No checker can verify that a syntactically valid citation points
to the *intended* symbol without understanding the prose; human
review still matters. Stop hooks can receive a missing final
message or hit the harness's continuation limit. Report those
cases as unverified; never claim absolute prevention from a skill
or hook configuration alone.
