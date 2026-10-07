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
    local source="$TMP_ROOT/shared-self-host" clone output first before_index
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
    # Source inference used to turn these tracked relative links into
    # absolute consumer links and create an anchor back to the source.
    # Both migration modes must preserve all bytes and the real index;
    # the clone below verifies the resulting portability contract.
    first="$(tree_digest "$source")"
    before_index="$(index_tree "$source")"
    output="$(bash "$source/scripts/deploy.sh" migrate "$source" --dry-run)"
    assert_contains "$output" 'preserve source-repository discovery links'
    assert_eq "$(tree_digest "$source")" "$first"
    bash "$source/scripts/deploy.sh" migrate "$source" >/dev/null
    assert_eq "$(tree_digest "$source")" "$first"
    assert_eq "$(index_tree "$source")" "$before_index"
    [ ! -L "$source/.ai/ai.skillz" ] || fail 'migration self-anchor'
    git -C "$source" commit --allow-empty -qm 'shared self-host fixture'
    clone="$TMP_ROOT/shared-self-host-clone"
    git clone -q "$source" "$clone"
    output="$(bash "$clone/scripts/deploy.sh" status "$clone")"
    assert_not_contains "$output" UNHEALTHY
    bash "$clone/scripts/validate-deployment.sh" "$clone" >/dev/null
    pass 'source-repo shared deployment is relative and cloneable'
}

test_shared_hybrid_alias_assets() {
    new_repo shared-hybrid-alias
    local provider asset output first
    bash "$DEPLOY" pr-msg "$REPO" --harness agents >/dev/null
    bash "$DEPLOY" pr-msg "$REPO" --harness all >/dev/null
    output="$(bash "$DEPLOY" status "$REPO" --harness agents)"
    assert_contains "$output" 'same-source alias in .claude'
    assert_contains "$output" 'same-source alias in .opencode'
    # Matching SKILL.md previously hid a divergent declared asset when
    # only the shared provider was selected. Exercise both directory
    # assets and both legacy providers, preserving local runtime files.
    for provider in .claude .opencode; do
        printf 'keep\n' > "$REPO/$provider/skills/pr-msg/local.txt"
        for asset in references scripts; do
            mkdir -p "$REPO/custom-$asset"
            ln -sfn "$REPO/custom-$asset" \
                "$REPO/$provider/skills/pr-msg/$asset"
            first="$(tree_digest "$REPO")"
            assert_fails bash "$DEPLOY" status "$REPO" --harness agents
            assert_file_contains "$TMP_ROOT/failure.out" \
                "divergent $provider definition"
            assert_eq "$(tree_digest "$REPO")" "$first"
            ln -sfn "$ROOT/skills/pr-msg/$asset" \
                "$REPO/$provider/skills/pr-msg/$asset"
        done
        assert_file_contains "$REPO/$provider/skills/pr-msg/local.txt" keep
    done
    bash "$DEPLOY" status "$REPO" --harness agents >/dev/null
    pass 'shared aliases compare every declared hybrid asset'
}

test_shared_parent_validation() {
    local parent value outside first output
    # Descendant-only index patterns missed parent symlinks entirely.
    # Empty external roots keep leaf validation from masking the bug;
    # replacing the working link proves the index is checked separately.
    for parent in .agents .agents/skills; do
        for value in absolute relative; do
            new_repo "shared-parent-${parent//\//_}-$value"
            outside="$REPO/external"
            mkdir -p "$outside" "$(dirname "$REPO/$parent")"
            if [ "$value" = absolute ]; then
                ln -s "$outside" "$REPO/$parent"
            elif [ "$parent" = .agents ]; then
                ln -s external "$REPO/$parent"
            else
                ln -s ../external "$REPO/$parent"
            fi
            git -C "$REPO" add "$parent"
            first="$(tree_digest "$REPO")"
            assert_fails bash "$DEPLOY" status "$REPO" --harness agents
            assert_file_contains "$TMP_ROOT/failure.out" 'symlinked parent'
            assert_fails bash "$ROOT/scripts/validate-deployment.sh" "$REPO"
            assert_file_contains "$TMP_ROOT/failure.out" \
                "committed shared parent link: $parent"
            assert_eq "$(tree_digest "$REPO")" "$first"
            rm "$REPO/$parent"
            mkdir "$REPO/$parent"
            assert_fails bash "$ROOT/scripts/validate-deployment.sh" "$REPO"
            assert_file_contains "$TMP_ROOT/failure.out" \
                "committed shared parent link: $parent"
        done
    done
    pass 'shared parent links are rejected in working tree and index'
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

test_repo_skill_relocation() {
    # Consumer-owned sources were invisible to manifest-only migration.
    # A committed fixture proves byte/mode preservation, index isolation,
    # relative adapters, clone portability, and repeatability.
    new_repo repo-skill-relocation
    local name before source_before clone
    for name in piker-profiling piker-slang pyqtgraph-optimization timeseries-optimization; do
        mkdir -p "$REPO/.claude/skills/$name"
        printf '%s\n' '---' "name: $name" 'description: local skill' '---' \
            > "$REPO/.claude/skills/$name/SKILL.md"
        printf 'resource\n' > "$REPO/.claude/skills/$name/resource.sh"
        chmod +x "$REPO/.claude/skills/$name/resource.sh"
        ln -s resource.sh "$REPO/.claude/skills/$name/resource-link"
    done
    git -C "$REPO" add .claude
    git -C "$REPO" commit -qm 'owned skills fixture'
    printf 'unrelated staged\n' > "$REPO/unrelated"
    git -C "$REPO" add unrelated
    before="$(index_tree "$REPO")"
    source_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run --stage
    assert_file_contains "$TMP_ROOT/failure.out" 'DECISION REQUIRED'
    assert_file_contains "$TMP_ROOT/failure.out" 'Agent-ready prompt:'
    for name in piker-profiling piker-slang pyqtgraph-optimization timeseries-optimization; do
        assert_file_contains "$TMP_ROOT/failure.out" ".claude/skills/$name"
    done
    assert_fails bash "$DEPLOY" migrate "$REPO"
    bash "$DEPLOY" migrate "$REPO" --repo-skills preserve --dry-run >/dev/null
    local preserved
    preserved="$(bash "$DEPLOY" migrate "$REPO" --repo-skills preserve --stage)"
    assert_contains "$preserved" '(not migrated)'
    assert_eq "$(index_tree "$REPO")" "$before"
    assert_eq "$(tree_digest "$REPO")" "$source_before"
    bash "$DEPLOY" migrate "$REPO" --repo-skills move --dry-run --stage >/dev/null
    assert_eq "$(index_tree "$REPO")" "$before"
    assert_eq "$(tree_digest "$REPO")" "$source_before"
    bash "$DEPLOY" migrate "$REPO" --repo-skills move >/dev/null
    assert_eq "$(index_tree "$REPO")" "$before"
    source_before="$(tree_digest "$REPO")"
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    assert_eq "$(tree_digest "$REPO")" "$source_before"
    for name in piker-profiling piker-slang pyqtgraph-optimization timeseries-optimization; do
        assert_eq "$(readlink "$REPO/.claude/skills/$name")" \
            "../../.agents/skills/$name"
        [ -x "$REPO/.agents/skills/$name/resource.sh" ] || fail 'mode lost'
        assert_eq "$(readlink "$REPO/.agents/skills/$name/resource-link")" resource.sh
        git -C "$REPO" add ".claude/skills/$name" ".agents/skills/$name"
    done
    git -C "$REPO" commit -qm 'relocation fixture'
    clone="$TMP_ROOT/repo-skill-clone"
    git clone -q "$REPO" "$clone"
    [ -f "$clone/.claude/skills/piker-slang/resource-link" ] || fail 'adapter broke in clone'
    bash "$ROOT/scripts/validate-deployment.sh" "$clone" >/dev/null

    new_repo repo-skill-stage
    mkdir -p "$REPO/.claude/skills/local-skill"
    printf 'local\n' > "$REPO/.claude/skills/local-skill/SKILL.md"
    git -C "$REPO" add .claude
    git -C "$REPO" commit -qm 'owned fixture'
    printf 'staged\n' > "$REPO/unrelated"
    git -C "$REPO" add unrelated
    before="$(index_entry "$REPO" unrelated)"
    bash "$DEPLOY" migrate "$REPO" --repo-skills move --stage >/dev/null
    assert_eq "$(index_entry "$REPO" unrelated)" "$before"
    assert_contains "$(index_entry "$REPO" .claude/skills/local-skill)" '120000'
    assert_contains "$(index_entry "$REPO" .agents/skills/local-skill/SKILL.md)" '100644'
    pass 'repository skills relocate with relative adapters and isolated staging'
}

test_repo_skill_refusals() {
    # A valid candidate must not move before a later conflict is found.
    # Snapshot both trees and the index across dry-run and apply failures.
    local scenario before index
    for scenario in dirty staged untracked ignored collision manifest parent external adapter-ignore destination-ignore; do
        new_repo "repo-skill-$scenario"
        mkdir -p "$REPO/.claude/skills/local-skill"
        printf 'local\n' > "$REPO/.claude/skills/local-skill/SKILL.md"
        git -C "$REPO" add .claude
        git -C "$REPO" commit -qm 'owned fixture'
        case "$scenario" in
            dirty|staged)
                printf 'changed\n' >> "$REPO/.claude/skills/local-skill/SKILL.md"
                [ "$scenario" != staged ] || git -C "$REPO" add .claude ;;
            untracked|ignored)
                printf secret > "$REPO/.claude/skills/local-skill/secret"
                [ "$scenario" != ignored ] || printf 'secret\n' > "$REPO/.gitignore" ;;
            collision) mkdir -p "$REPO/.agents/skills/local-skill" ;;
            manifest)
                mkdir -p "$REPO/.claude/skills/commit-msg"
                printf local > "$REPO/.claude/skills/commit-msg/SKILL.md"
                git -C "$REPO" add .claude
                git -C "$REPO" commit -qm collision ;;
            parent) ln -s "$TMP_ROOT" "$REPO/.agents" ;;
            adapter-ignore) printf '/.claude/skills/*\n' > "$REPO/.gitignore" ;;
            destination-ignore) printf '/.agents/\n' > "$REPO/.gitignore" ;;
            external)
                ln -s ../../../base.txt "$REPO/.claude/skills/local-skill/escape"
                git -C "$REPO" add .claude
                git -C "$REPO" commit -qm escape ;;
        esac
        before="$(tree_digest "$REPO")"
        index="$(index_tree "$REPO")"
        assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills move --dry-run
        assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills move --stage
        assert_eq "$(tree_digest "$REPO")" "$before"
        assert_eq "$(index_tree "$REPO")" "$index"
    done
    pass 'repository skill conflicts refuse without moving or staging content'
}

test_repo_skill_decision_gate() {
    # Previously only tracked clean trees were inventoried and moved
    # implicitly. Untracked/ignored definitions must also demand consent;
    # preserving them must neither move them nor authorize unsafe links.
    local scenario before index
    for scenario in untracked ignored dirty canonical; do
        new_repo "repo-skill-decision-$scenario"
        mkdir -p "$REPO/.claude/skills/local-skill"
        printf local > "$REPO/.claude/skills/local-skill/SKILL.md"
        case "$scenario" in
            ignored) printf '/.claude/skills/local-skill/\n' > "$REPO/.gitignore" ;;
            dirty)
                git -C "$REPO" add .claude
                git -C "$REPO" commit -qm 'local definition'
                printf edited >> "$REPO/.claude/skills/local-skill/SKILL.md" ;;
            canonical)
                mkdir -p "$REPO/.claude/skills/commit-msg"
                ln -s "$ROOT/skills/commit-msg/SKILL.md" \
                    "$REPO/.claude/skills/commit-msg/SKILL.md"
                git -C "$REPO" add .claude
                git -C "$REPO" commit -qm 'unsafe tracked canonical link' ;;
        esac
        before="$(tree_digest "$REPO")"
        index="$(index_tree "$REPO")"
        assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
        assert_file_contains "$TMP_ROOT/failure.out" 'DECISION REQUIRED'
        assert_fails bash "$DEPLOY" migrate "$REPO"
        if [ "$scenario" = canonical ]; then
            assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills preserve
            assert_file_contains "$TMP_ROOT/failure.out" 'local provider destination is tracked'
            assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills move
            assert_file_contains "$TMP_ROOT/failure.out" 'local provider destination is tracked'
        else
            bash "$DEPLOY" migrate "$REPO" --repo-skills preserve --dry-run >/dev/null
            bash "$DEPLOY" migrate "$REPO" --repo-skills preserve --stage >/dev/null
            assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills move
        fi
        assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills
        assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills yes
        assert_fails bash "$DEPLOY" migrate "$REPO" --repo-skills move --repo-skills preserve
        assert_eq "$(tree_digest "$REPO")" "$before"
        assert_eq "$(index_tree "$REPO")" "$index"
    done
    pass 'unmanaged skill consent is explicit and cannot bypass canonical-link guards'
}

test_managed_hybrid_links() {
    # Whole-directory commit-plan links used to fail both deploy and
    # migration. Keep shared links intact while repairing legacy roots.
    local provider before index asset
    new_repo managed-hybrid
    bash "$DEPLOY" all "$REPO" --harness agents >/dev/null
    bash "$DEPLOY" all "$REPO" --harness all >/dev/null
    for provider in claude opencode; do
        rm "$REPO/.$provider/skills/commit-plan/SKILL.md" \
            "$REPO/.$provider/skills/commit-plan/scripts" \
            "$REPO/.$provider/skills/commit-plan/BENCHMARK.md"
        rmdir "$REPO/.$provider/skills/commit-plan"
        ln -s ../../.agents/skills/commit-plan "$REPO/.$provider/skills/commit-plan"
    done
    before="$(tree_digest "$REPO")"
    index="$(index_tree "$REPO")"
    assert_fails bash "$DEPLOY" status "$REPO"
    assert_file_contains "$TMP_ROOT/failure.out" 'repairable managed whole-directory hybrid link'
    bash "$DEPLOY" migrate "$REPO" --dry-run >/dev/null
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_eq "$(index_tree "$REPO")" "$index"
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    assert_eq "$(index_tree "$REPO")" "$index"
    [ -L "$REPO/.agents/skills/commit-plan" ] || fail 'shared link replaced'
    bash "$ROOT/scripts/validate-deployment.sh" "$REPO" >/dev/null
    for provider in claude opencode; do
        rm "$REPO/.$provider/skills/commit-plan/SKILL.md" \
            "$REPO/.$provider/skills/commit-plan/scripts" \
            "$REPO/.$provider/skills/commit-plan/BENCHMARK.md"
        rmdir "$REPO/.$provider/skills/commit-plan"
        ln -s "$ROOT/skills/commit-plan" "$REPO/.$provider/skills/commit-plan"
    done
    bash "$DEPLOY" commit-plan "$REPO" --harness all >/dev/null
    before="$(tree_digest "$REPO")"
    bash "$DEPLOY" commit-plan "$REPO" --harness all >/dev/null
    assert_eq "$(tree_digest "$REPO")" "$before"
    bash "$ROOT/scripts/validate-deployment.sh" "$REPO" >/dev/null
    pass 'managed hybrid directory links are diagnosed and repaired without changing shared links'
}

test_hybrid_portable_and_refusals() {
    # A tracked directory symlink must be removed from the index only
    # with --stage. A bad OpenCode destination must prevent even the
    # otherwise safe Claude conversion during a provider-all deploy.
    local action before index provider scenario clone
    for action in migrate deploy; do
        new_repo "portable-hybrid-$action"
        bash "$DEPLOY" init "$REPO" --method submodule \
            --url "$SOURCE_URL" --stage >/dev/null
        bash "$DEPLOY" all "$REPO" --harness all --stage >/dev/null
        rm "$REPO/.claude/skills/commit-plan/SKILL.md" \
            "$REPO/.claude/skills/commit-plan/scripts" \
            "$REPO/.claude/skills/commit-plan/BENCHMARK.md"
        rmdir "$REPO/.claude/skills/commit-plan"
        ln -s ../../.ai/ai.skillz/skills/commit-plan \
            "$REPO/.claude/skills/commit-plan"
        git -C "$REPO" add .claude/skills/commit-plan
        git -C "$REPO" commit -qm 'stale portable fixture'
        if [ "$action" = migrate ]; then
            before="$(tree_digest "$REPO")"
            index="$(index_tree "$REPO")"
            bash "$DEPLOY" migrate "$REPO" --dry-run --stage >/dev/null
            assert_eq "$(tree_digest "$REPO")" "$before"
            assert_eq "$(index_tree "$REPO")" "$index"
            bash "$DEPLOY" migrate "$REPO" --stage >/dev/null
        else
            bash "$DEPLOY" commit-plan "$REPO" --harness all --stage >/dev/null
        fi
        assert_contains "$(index_entry "$REPO" .claude/skills/commit-plan/SKILL.md)" '120000'
        assert_eq "$(readlink "$REPO/.claude/skills/commit-plan/scripts")" \
            '../../../.ai/ai.skillz/skills/commit-plan/scripts'
        git -C "$REPO" commit -qm 'repaired portable fixture'
        clone="$TMP_ROOT/portable-hybrid-$action-clone"
        git -c protocol.file.allow=always clone -q --recurse-submodules "$REPO" "$clone"
        bash "$ROOT/scripts/validate-deployment.sh" "$clone" >/dev/null
    done
    for scenario in broken unmanaged different-source; do
        new_repo "hybrid-refusal-$scenario"
        bash "$DEPLOY" all "$REPO" --harness all >/dev/null
        for provider in claude opencode; do
            rm "$REPO/.$provider/skills/commit-plan/SKILL.md" \
                "$REPO/.$provider/skills/commit-plan/scripts" \
                "$REPO/.$provider/skills/commit-plan/BENCHMARK.md"
            rmdir "$REPO/.$provider/skills/commit-plan"
        done
        ln -s "$ROOT/skills/commit-plan" "$REPO/.claude/skills/commit-plan"
        case "$scenario" in
            broken) ln -s missing "$REPO/.opencode/skills/commit-plan" ;;
            unmanaged) ln -s "$REPO" "$REPO/.opencode/skills/commit-plan" ;;
            different-source) ln -s "$SOURCE_WORK/skills/commit-plan" "$REPO/.opencode/skills/commit-plan" ;;
        esac
        before="$(tree_digest "$REPO")"
        index="$(index_tree "$REPO")"
        assert_fails bash "$DEPLOY" commit-plan "$REPO" --harness all
        assert_eq "$(tree_digest "$REPO")" "$before"
        assert_fails bash "$DEPLOY" migrate "$REPO"
        assert_eq "$(tree_digest "$REPO")" "$before"
        assert_eq "$(index_tree "$REPO")" "$index"
    done
    pass 'portable hybrid repairs survive clones and unsafe multi-provider repairs are refused'
}

run_shared_cases() {
    test_repo_skill_decision_gate
    test_hybrid_portable_and_refusals
    test_repo_skill_relocation
    test_repo_skill_refusals
    test_managed_hybrid_links
    test_shared_local_and_commands
    test_shared_global_ownership
    test_shared_portable_clone
    test_shared_self_hosting
    test_shared_hybrid_alias_assets
    test_shared_parent_validation
    test_shared_collisions_and_parents
    test_shared_migration
    python3 "$ROOT/tests/deploy/test-codex-regressions.py"
    pass 'Codex probe rejects invalid responses with and without optimization'
}
