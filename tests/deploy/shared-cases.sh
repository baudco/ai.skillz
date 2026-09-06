# Shared discovery regressions, sourced by test-deploy.sh.

test_shared_local_and_commands() {
    new_repo shared-local
    local source_before output first
    source_before="$(tree_digest "$ROOT/skills")"
    bash "$DEPLOY" all "$REPO" --harness codex >/dev/null
    assert_eq "$(readlink "$REPO/.agents/skills/commit-plan")" \
        "$ROOT/skills/commit-plan"
    [ ! -e "$REPO/.codex" ] || fail 'unexpected Codex-specific tree'
    [ ! -e "$REPO/.opencode/skills" ] || fail 'duplicate skill tree'
    [ -L "$REPO/.agents/skills/pr-msg" ] \
        || fail 'hybrid invocation metadata not linked'
    git -C "$REPO" check-ignore -q .agents/skills/commit-plan \
        || fail 'local shared link is not ignored'
    first="$(tree_digest "$REPO")"
    bash "$DEPLOY" all "$REPO" --provider agents >/dev/null
    assert_eq "$(tree_digest "$REPO")" "$first"
    bash "$DEPLOY" command all "$REPO" \
        --harness opencode >/dev/null
    output="$(bash "$DEPLOY" status "$REPO")"
    assert_contains "$output" 'Provider agents: enabled'
    assert_not_contains "$output" UNHEALTHY
    assert_eq "$(tree_digest "$ROOT/skills")" "$source_before"

    # A broken explicit deployment must not be hidden by the shared one.
    mkdir -p "$REPO/.opencode/skills"
    ln -s missing "$REPO/.opencode/skills/commit-msg"
    first="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" command commit-plan "$REPO" \
        --harness opencode
    assert_eq "$(tree_digest "$REPO")" "$first"
    pass 'shared local aliases, hybrid metadata, and OpenCode dependencies'
}

test_shared_global_ownership() {
    local global_home="$TMP_ROOT/shared-global-home" first
    mkdir -p "$global_home/.claude/skills/pr-msg"
    printf 'keep\n' > "$global_home/.claude/skills/pr-msg/local.txt"
    env HOME="$global_home" bash "$DEPLOY" pr-msg \
        --global --harness codex >/dev/null
    env HOME="$global_home" bash "$DEPLOY" py-codestyle \
        --global --provider agents >/dev/null
    [ -L "$global_home/.agents/skills/pr-msg" ] \
        || fail 'missing global hybrid sidecar'
    assert_file_contains \
        "$global_home/.claude/skills/pr-msg/local.txt" keep
    first="$(tree_digest "$global_home")"
    env HOME="$global_home" bash "$DEPLOY" pr-msg \
        --global --harness codex >/dev/null
    assert_eq "$(tree_digest "$global_home")" "$first"
    assert_fails env HOME="$global_home" bash "$DEPLOY" \
        command all --global --harness codex

    global_home="$TMP_ROOT/shared-owned-home"
    mkdir -p "$global_home/.agents" "$global_home/dotrc-skills"
    ln -s "$global_home/dotrc-skills" "$global_home/.agents/skills"
    first="$(tree_digest "$global_home")"
    assert_fails env HOME="$global_home" bash "$DEPLOY" \
        py-codestyle --global --harness codex
    assert_eq "$(tree_digest "$global_home")" "$first"
    pass 'shared global install preserves files and refuses another owner'
}

test_shared_portable_clone() {
    new_repo shared-portable
    bash "$DEPLOY" init "$REPO" --method submodule \
        --url "$SOURCE_URL" --stage >/dev/null
    mkdir -p "$REPO/.claude/skills/commit-msg/msgs"
    printf 'archive\n' > "$REPO/.claude/skills/commit-msg/msgs/keep"
    bash "$DEPLOY" all "$REPO" --harness agents --stage >/dev/null
    assert_file_contains "$REPO/.claude/skills/commit-msg/msgs/keep" \
        archive
    assert_eq "$(readlink "$REPO/.agents/skills/commit-plan")" \
        '../../.ai/ai.skillz/skills/commit-plan'
    assert_eq "$(readlink "$REPO/.agents/skills/pr-msg")" \
        '../../.ai/ai.skillz/skills/pr-msg'
    git -C "$REPO" commit -qm 'shared portable fixture'
    local clone="$TMP_ROOT/shared-clone"
    git -c protocol.file.allow=always clone -q --recurse-submodules \
        "$REPO" "$clone"
    [ -f "$clone/.agents/skills/commit-plan/SKILL.md" ] \
        || fail 'generic shared skill does not survive clone'
    [ -f "$clone/.agents/skills/pr-msg/agents/openai.yaml" ] \
        || fail 'hybrid metadata does not survive clone'
    bash "$ROOT/scripts/validate-deployment.sh" "$clone" >/dev/null

    # Validate the Git index, not just what the current symlink resolves to.
    ln -sfn "$ROOT/skills/commit-plan" \
        "$clone/.agents/skills/commit-plan"
    git -C "$clone" add .agents/skills/commit-plan
    assert_fails bash "$ROOT/scripts/validate-deployment.sh" "$clone"
    assert_file_contains "$TMP_ROOT/failure.out" \
        'committed absolute provider link: .agents/skills/commit-plan'
    pass 'portable shared links and sidecars survive a fresh clone'
}

test_shared_self_hosting() {
    local source="$TMP_ROOT/shared-self-host" clone output
    git clone -q "$SOURCE_WORK" "$source"
    git -C "$source" config user.email fixture@example.com
    git -C "$source" config user.name Fixture
    bash "$source/scripts/deploy.sh" all "$source" \
        --harness codex --stage >/dev/null
    assert_eq "$(readlink "$source/.agents/skills/commit-plan")" \
        '../../skills/commit-plan'
    assert_eq "$(readlink "$source/.agents/skills/pr-msg")" \
        '../../skills/pr-msg'
    [ ! -e "$source/.ai/ai.skillz" ] || fail 'self-hosting anchor'
    git -C "$source" commit --allow-empty -qm 'shared self-host fixture'
    clone="$TMP_ROOT/shared-self-host-clone"
    git clone -q "$source" "$clone"
    output="$(bash "$clone/scripts/deploy.sh" status "$clone")"
    assert_not_contains "$output" UNHEALTHY
    bash "$clone/scripts/validate-deployment.sh" "$clone" >/dev/null
    pass 'source-repo shared deployment is relative and cloneable'
}

test_shared_collisions_and_parents() {
    new_repo shared-collision
    local output first
    bash "$DEPLOY" py-codestyle "$REPO" --harness agents >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    output="$(bash "$DEPLOY" status "$REPO")"
    assert_contains "$output" 'same-source alias in .claude'
    assert_contains "$output" 'same-source alias in .opencode'
    # An existing definition with different instructions is ambiguous.
    mkdir -p "$REPO/custom-skill"
    cp "$ROOT/skills/py-codestyle/SKILL.md" \
        "$REPO/custom-skill/SKILL.md"
    ln -sfn "$REPO/custom-skill" "$REPO/.claude/skills/py-codestyle"
    assert_fails bash "$DEPLOY" status "$REPO" --harness codex
    assert_file_contains "$TMP_ROOT/failure.out" \
        'divergent .claude definition'

    new_repo shared-parent
    mkdir -p "$TMP_ROOT/shared-external"
    ln -s "$TMP_ROOT/shared-external" "$REPO/.agents"
    first="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" all "$REPO" --harness agents
    assert_eq "$(tree_digest "$REPO")" "$first"
    [ -z "$(ls -A "$TMP_ROOT/shared-external")" ] \
        || fail 'deployment wrote through shared parent symlink'
    pass 'shared collisions are visible and parent ownership is enforced'
}

test_shared_migration() {
    new_repo shared-migration
    local first
    bash "$DEPLOY" py-codestyle "$REPO" --harness codex >/dev/null
    bash "$DEPLOY" init "$REPO" --method submodule \
        --url "$SOURCE_URL" >/dev/null
    first="$(tree_digest "$REPO")"
    bash "$DEPLOY" migrate "$REPO" --dry-run >/dev/null
    assert_eq "$(tree_digest "$REPO")" "$first"
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    assert_eq "$(readlink "$REPO/.agents/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'
    bash "$ROOT/scripts/validate-deployment.sh" "$REPO" >/dev/null
    pass 'shared direct deployments participate in anchor migration'
}

run_shared_cases() {
    test_shared_local_and_commands
    test_shared_global_ownership
    test_shared_portable_clone
    test_shared_self_hosting
    test_shared_collisions_and_parents
    test_shared_migration
}
