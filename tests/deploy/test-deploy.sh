#!/usr/bin/env bash

set -euo pipefail

TEST_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$TEST_DIR/../.." && pwd -P)"
DEPLOY="$ROOT/scripts/deploy.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-deploy-tests.XXXXXX")"
PASS=0

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

pass() {
    PASS=$((PASS + 1))
    printf 'ok %d - %s\n' "$PASS" "$1"
}

assert_eq() {
    [ "$1" = "$2" ] || fail "expected '$2', got '$1'"
}

assert_contains() {
    case "$1" in *"$2"*) ;; *) fail "output does not contain: $2" ;; esac
}

assert_not_contains() {
    case "$1" in *"$2"*) fail "output unexpectedly contains: $2" ;; *) ;; esac
}

assert_file_contains() {
    grep -qF -- "$2" "$1" || fail "$1 does not contain: $2"
}

assert_fails() {
    if "$@" >"$TMP_ROOT/failure.out" 2>&1; then
        fail "command unexpectedly succeeded: $*"
    fi
}

new_repo() {
    local name="$1"
    REPO="$TMP_ROOT/$name"
    mkdir -p "$REPO"
    git -C "$REPO" init -q
    git -C "$REPO" config user.email fixture@example.com
    git -C "$REPO" config user.name Fixture
    printf 'base\n' > "$REPO/base.txt"
    git -C "$REPO" add base.txt
    git -C "$REPO" commit -qm fixture
}

file_digest() {
    cksum < "$1"
}

tree_digest() {
    (
        cd "$1"
        find . -path ./.git -prune -o \( -type f -o -type l \) -print \
            | LC_ALL=C sort \
            | while IFS= read -r path; do
                if [ -L "$path" ]; then
                    printf 'L %s %s\n' "$path" "$(readlink "$path")"
                else
                    printf 'F %s ' "$path"
                    cksum < "$path"
                fi
            done
    ) | cksum
}

index_tree() {
    git -C "$1" write-tree
}

index_entry() {
    git -C "$1" ls-files -s -- "$2"
}

mode_string() {
    local listing
    listing="$(LC_ALL=C ls -ld "$1")"
    printf '%s\n' "${listing%% *}"
}

count_fixed() {
    grep -cF -- "$2" "$1" 2>/dev/null || true
}

prepare_source_repo() {
    SOURCE_WORK="$TMP_ROOT/source-work"
    git clone -q "$ROOT" "$SOURCE_WORK"
    git -C "$SOURCE_WORK" config user.email fixture@example.com
    git -C "$SOURCE_WORK" config user.name Fixture
    mkdir -p "$SOURCE_WORK/providers/opencode/commands" "$SOURCE_WORK/tests/deploy"
    cp "$ROOT/providers/opencode/commands/commit-msg.md" \
        "$SOURCE_WORK/providers/opencode/commands/commit-msg.md"
    cp "$ROOT/deploy-manifest.conf" "$SOURCE_WORK/deploy-manifest.conf"
    cp "$ROOT/gitignore-patterns.conf" "$SOURCE_WORK/gitignore-patterns.conf"
    cp "$ROOT/scripts/deploy.sh" "$SOURCE_WORK/scripts/deploy.sh"
    cp "$ROOT/scripts/validate-deployment.sh" \
        "$SOURCE_WORK/scripts/validate-deployment.sh"
    chmod +x "$SOURCE_WORK/scripts/deploy.sh" \
        "$SOURCE_WORK/scripts/validate-deployment.sh"
    git -C "$SOURCE_WORK" add deploy-manifest.conf gitignore-patterns.conf \
        scripts/deploy.sh scripts/validate-deployment.sh \
        providers/opencode/commands/commit-msg.md
    git -C "$SOURCE_WORK" commit -qm 'fixture deployment source'
    SOURCE_URL="file://$SOURCE_WORK"
}

test_local_anchor_and_anchor_authority() {
    new_repo local-anchor
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'
    assert_eq "$(readlink "$REPO/.opencode/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'

    local alternate="$TMP_ROOT/alternate-source"
    git clone -q "$SOURCE_WORK" "$alternate"
    printf '\nanchor-specific\n' >> "$alternate/skills/py-codestyle/SKILL.md"
    new_repo anchor-authority
    mkdir -p "$REPO/.ai"
    ln -s "$alternate" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    grep -q anchor-specific "$REPO/.opencode/skills/py-codestyle/SKILL.md" \
        || fail 'anchored skill did not resolve through target anchor'
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    printf '\nanchor-command\n' >> "$alternate/providers/opencode/commands/commit-msg.md"
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    grep -q anchor-command "$REPO/.opencode/commands/commit-msg.md" \
        || fail 'command source did not come from target anchor'
    pass 'anchored skill and command sources come only from target anchor'
}

test_subdirectory_resolves_repository_root() {
    new_repo subdirectory-target
    mkdir -p "$REPO/nested/deep"
    bash "$DEPLOY" init "$REPO/nested/deep" --method symlink >/dev/null
    [ -L "$REPO/.ai/ai.skillz" ] || fail 'anchor was not created at repository root'
    [ ! -e "$REPO/nested/deep/.ai" ] || fail 'anchor was created under subdirectory'
    bash "$DEPLOY" py-codestyle "$REPO/nested" --provider opencode >/dev/null
    [ -L "$REPO/.opencode/skills/py-codestyle" ] \
        || fail 'provider skill was not deployed at repository root'
    pass 'subdirectory targets canonicalize to git repository root'
}

test_submodule_and_portable_default_url() {
    new_repo submodule
    local before
    before="$(index_tree "$REPO")"
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    assert_eq "$(index_tree "$REPO")" "$before"
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    assert_eq "$(readlink "$REPO/.opencode/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'

    local parent="$TMP_ROOT/portable-default"
    mkdir -p "$parent"
    git clone -q --bare "$SOURCE_WORK" "$parent/ai.skillz.git"
    REPO="$parent/consumer"
    mkdir -p "$REPO"
    git -C "$REPO" init -q
    git -C "$REPO" config user.email fixture@example.com
    git -C "$REPO" config user.name Fixture
    git -C "$REPO" remote add origin "file://$parent/consumer.git"
    printf base > "$REPO/base"
    git -C "$REPO" add base
    git -C "$REPO" commit -qm fixture
    bash "$DEPLOY" init "$REPO" --method submodule >/dev/null
    assert_eq "$(git -C "$REPO" config -f .gitmodules \
        --get-regexp '^submodule\..*\.url$' | while read -r _ value; do printf '%s' "$value"; done)" \
        '../ai.skillz.git'
    pass 'submodule deployment is unstaged and default URL is portable'
}

test_init_stage_preserves_gitmodules_index() {
    new_repo staged-gitmodules
    printf '# committed\n' > "$REPO/.gitmodules"
    git -C "$REPO" add .gitmodules
    git -C "$REPO" commit -qm gitmodules
    printf '# staged-user-line\n' >> "$REPO/.gitmodules"
    git -C "$REPO" add .gitmodules
    printf '# unstaged-user-line\n' >> "$REPO/.gitmodules"
    printf staged > "$REPO/staged.txt"
    git -C "$REPO" add staged.txt
    local staged_entry
    staged_entry="$(index_entry "$REPO" staged.txt)"
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" --stage >/dev/null
    assert_eq "$(index_entry "$REPO" staged.txt)" "$staged_entry"
    git -C "$REPO" show :.gitmodules | grep -q '# staged-user-line' \
        || fail 'preexisting staged .gitmodules content was lost'
    git -C "$REPO" show :.gitmodules | grep -q '# unstaged-user-line' \
        && fail 'unrelated unstaged .gitmodules content was absorbed'
    git -C "$REPO" show :.gitmodules | grep -q 'path = .ai/ai.skillz' \
        || fail 'tool-generated submodule path was not staged'
    grep -q '# unstaged-user-line' "$REPO/.gitmodules" \
        || fail 'unstaged .gitmodules content was removed from worktree'
    pass 'init --stage merges only generated submodule section into existing index'
}

test_phase0_and_global_compatibility() {
    new_repo phase0
    local output staged_names
    bash "$DEPLOY" commit-msg "$REPO" >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" --provider opencode --method symlink >/dev/null
    [ "$(readlink "$REPO/.claude/skills/commit-msg/SKILL.md")" = \
        "$ROOT/skills/commit-msg/SKILL.md" ] || fail 'legacy Claude direct default was not restored'
    [ "$(readlink "$REPO/.opencode/skills/py-codestyle")" = \
        "$ROOT/skills/py-codestyle" ] || fail 'OpenCode Phase-0 direct mode was not restored'
    bash "$DEPLOY" py-codestyle "$REPO" --provider all --method symlink --stage >/dev/null
    staged_names="$(git -C "$REPO" diff --cached --name-only)"
    assert_eq "$staged_names" '.gitignore'
    git -C "$REPO" ls-files -s | grep -q 'skills/py-codestyle' \
        && fail 'absolute link was staged'
    output="$(HOME="$TMP_ROOT/home" bash "$DEPLOY" command \
        branch-in-new-terminal --global)"
    [ -L "$TMP_ROOT/home/.claude/commands/branch-in-new-terminal.md" ] \
        || fail 'global Claude command was not linked'
    assert_contains "$output" 'Companion hook'
    pass 'Phase-0 defaults, no absolute staging, and Claude --global remain compatible'
}

test_exact_staging_and_index_preservation() {
    new_repo exact-stage
    mkdir -p "$REPO/.claude/skills/commit-msg/msgs"
    printf old > "$REPO/.claude/skills/commit-msg/msgs/state.md"
    printf old > "$REPO/unrelated.txt"
    git -C "$REPO" add .claude/skills/commit-msg/msgs/state.md unrelated.txt
    git -C "$REPO" commit -qm state
    printf staged-runtime > "$REPO/.claude/skills/commit-msg/msgs/state.md"
    printf staged-unrelated > "$REPO/unrelated.txt"
    git -C "$REPO" add .claude/skills/commit-msg/msgs/state.md unrelated.txt
    printf unstaged-user > "$REPO/.claude/skills/commit-msg/user-state.txt"
    local runtime_before unrelated_before
    runtime_before="$(index_entry "$REPO" .claude/skills/commit-msg/msgs/state.md)"
    unrelated_before="$(index_entry "$REPO" unrelated.txt)"
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    printf 'unstaged-ignore-user-line\n' >> "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider all --stage >/dev/null
    assert_eq "$(index_entry "$REPO" .claude/skills/commit-msg/msgs/state.md)" "$runtime_before"
    assert_eq "$(index_entry "$REPO" unrelated.txt)" "$unrelated_before"
    [ -z "$(index_entry "$REPO" .claude/skills/commit-msg/user-state.txt)" ] \
        || fail 'user runtime state was staged'
    git -C "$REPO" ls-files -s -- .claude/skills/commit-msg/SKILL.md \
        | grep -q '^120000 ' || fail 'canonical hybrid link was not staged'
    git -C "$REPO" show :.gitignore | grep -q '# BEGIN ai.skillz: runtime:commit-msg' \
        || fail 'tool-owned ignore block was not staged'
    git -C "$REPO" show :.gitignore | grep -q unstaged-ignore-user-line \
        && fail 'unrelated unstaged .gitignore line was staged'
    pass '--stage touches only exact canonical artifacts and preserves index entries'
}

test_managed_replacement_safety() {
    new_repo replacement-safety
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    mkdir -p "$REPO/.claude/skills" "$REPO/unmanaged"
    ln -s "$REPO/unmanaged" "$REPO/.claude/skills/py-codestyle"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO"
    assert_eq "$(readlink "$REPO/.claude/skills/py-codestyle")" "$REPO/unmanaged"

    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    mkdir -p "$REPO/.opencode/commands"
    printf 'user command\n' > "$REPO/.opencode/commands/commit-msg.md"
    assert_fails bash "$DEPLOY" command commit-msg "$REPO" --provider opencode
    assert_eq "$(<"$REPO/.opencode/commands/commit-msg.md")" 'user command'

    new_repo recognized-transition
    bash "$DEPLOY" py-codestyle "$REPO" >/dev/null
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'
    pass 'only positively recognized links and copied commands are replaceable'
}

test_provider_all_skill_preflight() {
    new_repo provider-all-preflight
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    mkdir -p "$REPO/.opencode/skills/py-codestyle"
    printf user > "$REPO/.opencode/skills/py-codestyle/user.txt"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider all
    [ ! -e "$REPO/.claude/skills/py-codestyle" ] \
        || fail 'Claude destination mutated before OpenCode preflight failed'
    assert_eq "$(<"$REPO/.opencode/skills/py-codestyle/user.txt")" user
    pass 'provider-all skill deployment preflights every destination before mutation'
}

test_external_gitignore_symlink_refusal() {
    new_repo external-ignore
    local external="$TMP_ROOT/external-ignore-file" before tree_before
    printf external-user-content > "$external"
    ln -s "$external" "$REPO/.gitignore"
    before="$(file_digest "$external")"
    tree_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider opencode
    assert_contains "$(<"$TMP_ROOT/failure.out")" '.gitignore symlink outside repository'
    assert_eq "$(file_digest "$external")" "$before"
    assert_eq "$(tree_digest "$REPO")" "$tree_before"
    pass 'external .gitignore symlinks are refused before any mutation'
}

test_external_provider_parent_refusal() {
    local external before target_before

    new_repo external-claude-root
    external="$TMP_ROOT/external-claude-root-dir"
    mkdir -p "$external"
    ln -s "$external" "$REPO/.claude"
    before="$(tree_digest "$external")"
    target_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider claude
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'provider parent symlink outside repository'
    assert_eq "$(tree_digest "$external")" "$before"
    assert_eq "$(tree_digest "$REPO")" "$target_before"

    new_repo external-opencode-root
    external="$TMP_ROOT/external-opencode-root-dir"
    mkdir -p "$external"
    ln -s "$external" "$REPO/.opencode"
    before="$(tree_digest "$external")"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider opencode
    assert_eq "$(tree_digest "$external")" "$before"

    new_repo external-skills-parent
    external="$TMP_ROOT/external-skills-dir"
    mkdir -p "$external" "$REPO/.opencode"
    ln -s "$external" "$REPO/.opencode/skills"
    before="$(tree_digest "$external")"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider opencode
    assert_eq "$(tree_digest "$external")" "$before"

    new_repo external-commands-parent
    external="$TMP_ROOT/external-commands-dir"
    mkdir -p "$external" "$REPO/.claude"
    ln -s "$external" "$REPO/.claude/commands"
    before="$(tree_digest "$external")"
    assert_fails bash "$DEPLOY" command branch-in-new-terminal "$REPO"
    assert_eq "$(tree_digest "$external")" "$before"

    new_repo external-hybrid-parent
    external="$TMP_ROOT/external-hybrid-dir"
    mkdir -p "$external" "$REPO/.opencode/skills"
    ln -s "$external" "$REPO/.opencode/skills/pr-msg"
    before="$(tree_digest "$external")"
    assert_fails bash "$DEPLOY" pr-msg "$REPO" --provider opencode
    assert_eq "$(tree_digest "$external")" "$before"
    pass 'external provider roots, type directories, and destination parents refuse without mutation'
}

test_direct_opencode_with_existing_claude_and_config() {
    new_repo direct-both-existing
    bash "$DEPLOY" commit-msg "$REPO" >/dev/null
    printf claude-state > "$REPO/.claude/skills/commit-msg/local-state.txt"
    local claude_link config_before output
    claude_link="$(readlink "$REPO/.claude/skills/commit-msg/SKILL.md")"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode --method symlink >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/commit-msg/SKILL.md")" "$claude_link"
    assert_eq "$(<"$REPO/.claude/skills/commit-msg/local-state.txt")" claude-state
    [ -L "$REPO/.opencode/skills/commit-msg/SKILL.md" ] \
        || fail 'direct OpenCode skill was not deployed beside Claude skill'
    printf '{"skills":{"paths":["/tmp/path with spaces/skills"]}}\n' \
        > "$REPO/opencode.json"
    config_before="$(file_digest "$REPO/opencode.json")"
    assert_fails bash "$DEPLOY" status "$REPO"
    output="$(<"$TMP_ROOT/failure.out")"
    assert_contains "$output" 'Provider claude: enabled'
    assert_contains "$output" 'Provider opencode: enabled'
    assert_contains "$output" 'local-only (absolute)'
    assert_contains "$output" '/tmp/path with spaces/skills'
    assert_eq "$(file_digest "$REPO/opencode.json")" "$config_before"
    pass 'direct OpenCode coexists with Claude and reports absolute skills.paths without edits'
}

test_missing_anchor_assets_and_command_preflight() {
    local old="$TMP_ROOT/old-source"
    git clone -q "$SOURCE_WORK" "$old"
    rm "$old/providers/opencode/commands/commit-msg.md"
    new_repo old-anchor
    mkdir -p "$REPO/.ai"
    ln -s "$old" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    assert_fails bash "$DEPLOY" command all "$REPO" --provider all
    [ ! -e "$REPO/.claude/commands/branch-in-new-terminal.md" ] \
        || fail 'command preflight partially deployed another provider'
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'command source missing from deployment source'

    rm "$old/skills/py-codestyle/SKILL.md"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider claude
    pass 'older anchors missing canonical assets are refused before partial deployment'
}

test_runtime_ignores_and_state_preservation() {
    new_repo runtime
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    mkdir -p "$REPO/.claude/skills/commit-msg/msgs"
    printf keep > "$REPO/.claude/skills/commit-msg/msgs/old.md"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    assert_eq "$(<"$REPO/.claude/skills/commit-msg/msgs/old.md")" keep
    assert_file_contains "$REPO/.gitignore" '.claude/skills/commit-msg/msgs/'
    assert_not_contains "$(<"$REPO/.gitignore")" '.opencode/skills/commit-msg/msgs/'
    pass 'OpenCode deployment preserves and ignores canonical .claude runtime state'
}

test_command_dependency_all_and_hooks() {
    new_repo command-dependency
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    assert_fails bash "$DEPLOY" command commit-msg "$REPO" --provider opencode
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'requires healthy opencode skill'
    mkdir -p "$REPO/.opencode/commands"
    cp "$ROOT/providers/opencode/commands/commit-msg.md" \
        "$REPO/.opencode/commands/commit-msg.md"
    assert_fails bash "$DEPLOY" status "$REPO" --provider opencode
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'dependency skill commit-msg missing or unhealthy'
    rm "$REPO/.opencode/commands/commit-msg.md"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    local output
    output="$(bash "$DEPLOY" command commit-msg "$REPO" --provider all)"
    assert_contains "$output" 'unsupported skipped'
    [ -f "$REPO/.opencode/commands/commit-msg.md" ] \
        || fail 'supported OpenCode command was skipped'
    output="$(bash "$DEPLOY" command branch-in-new-terminal "$REPO" --provider all)"
    assert_contains "$output" 'Companion hook'
    assert_contains "$output" 'unsupported skipped'
    pass 'command dependencies, provider-all skips, and hook reporting are enforced'
}

test_status_health_templates_and_source_symlink() {
    new_repo status
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    rm "$REPO/.opencode/skills/py-codestyle"
    ln -s '../../.ai/ai.skillz/skills/missing' "$REPO/.opencode/skills/py-codestyle"
    assert_fails bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'broken ->'

    new_repo template-status
    mkdir -p "$REPO/.claude/skills/run-tests"
    printf '%s\n' '---' 'name: run-tests' 'description: local' '---' \
        > "$REPO/.claude/skills/run-tests/SKILL.md"
    assert_contains "$(bash "$DEPLOY" status "$REPO" --provider claude)" \
        'local template [healthy]'

    local source_repo="$TMP_ROOT/source-status"
    git clone -q "$SOURCE_WORK" "$source_repo"
    mkdir -p "$source_repo/.opencode/commands"
    rm -f "$source_repo/.opencode/commands/commit-msg.md"
    ln -s '../../providers/opencode/commands/commit-msg.md' \
        "$source_repo/.opencode/commands/commit-msg.md"
    [ ! -e "$source_repo/.opencode/skills/commit-msg" ] \
        || fail 'self-hosting fixture unexpectedly has explicit skill link'
    mkdir -p "$source_repo/.claude/skills/commit-msg/msgs"
    printf 'session = "runtime"\n' \
        > "$source_repo/.claude/skills/commit-msg/conf.toml"
    printf runtime > "$source_repo/.claude/skills/commit-msg/msgs/current.md"
    local source_status
    source_status="$(bash "$source_repo/scripts/deploy.sh" status "$source_repo")"
    assert_contains "$source_status" 'runtime-state-only (not deployed) [healthy]'
    assert_contains "$source_status" 'intentional source-repo symlink [healthy]'
    "$source_repo/scripts/validate-deployment.sh" "$source_repo" >/dev/null
    ln -s "$source_repo/skills/commit-msg/missing" \
        "$source_repo/.claude/skills/commit-msg/SKILL.md"
    assert_fails bash "$source_repo/scripts/deploy.sh" status "$source_repo"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'broken ->'
    pass 'status catches broken links and accepts templates/source-repo command links'
}

test_gitignore_integrity_and_inventory() {
    new_repo ignore-integrity
    mkdir -p "$REPO/config"
    printf 'user-line\n' > "$REPO/config/ignore"
    chmod 640 "$REPO/config/ignore"
    ln -s config/ignore "$REPO/.gitignore"
    local mode_before
    mode_before="$(mode_string "$REPO/config/ignore")"
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    [ -L "$REPO/.gitignore" ] || fail '.gitignore symlink was replaced'
    assert_eq "$(mode_string "$REPO/config/ignore")" "$mode_before"
    assert_file_contains "$REPO/config/ignore" user-line
    bash "$DEPLOY" gitignore "$REPO" >/dev/null
    assert_file_contains "$REPO/config/ignore" '.claude/.current_session'
    assert_file_contains "$REPO/config/ignore" '.claude/skills/commit-msg/msgs/'
    assert_file_contains "$REPO/config/ignore" '.claude/review_regression.md'

    printf '\n# END ai.skillz: bad\n' >> "$REPO/config/ignore"
    local before
    before="$(file_digest "$REPO/config/ignore")"
    assert_fails bash "$DEPLOY" gitignore "$REPO"
    assert_eq "$(file_digest "$REPO/config/ignore")" "$before"
    pass 'gitignore updates preserve links/modes/user lines and validate all markers'
}

test_direct_migration_dry_run() {
    new_repo direct-migration
    bash "$DEPLOY" commit-msg "$REPO" --provider all >/dev/null
    bash "$DEPLOY" command branch-in-new-terminal "$REPO" >/dev/null
    mkdir -p "$REPO/.opencode"
    printf '{"permission":{"bash":"ask"}}\n' > "$REPO/.opencode/opencode.json"
    local before after dry real config_before dry_actions real_actions
    before="$(tree_digest "$REPO")"
    config_before="$(file_digest "$REPO/.opencode/opencode.json")"
    dry="$(bash "$DEPLOY" migrate "$REPO" --dry-run)"
    after="$(tree_digest "$REPO")"
    assert_eq "$after" "$before"
    real="$(bash "$DEPLOY" migrate "$REPO")"
    dry_actions="$(printf '%s\n' "$dry" | while IFS= read -r line; do
        case "$line" in Would\ *) printf '%s\n' "${line#Would }" ;; esac
    done)"
    real_actions="$(printf '%s\n' "$real" | while IFS= read -r line; do
        case "$line" in 'Migration inspection complete;'*) ;; *) printf '%s\n' "$line" ;; esac
    done)"
    assert_eq "$real_actions" "$dry_actions"
    assert_eq "$(file_digest "$REPO/.opencode/opencode.json")" "$config_before"
    assert_eq "$(readlink "$REPO/.claude/skills/commit-msg/SKILL.md")" \
        '../../../.ai/ai.skillz/skills/commit-msg/SKILL.md'
    pass 'direct migration dry-run exactly predicts real actions without mutation'
}

test_migration_full_preflight_zero_mutation() {
    local second_source="$TMP_ROOT/second-migration-source"
    git clone -q "$SOURCE_WORK" "$second_source"
    new_repo mixed-migration
    mkdir -p "$REPO/.claude/skills" "$REPO/.opencode/skills"
    ln -s "$SOURCE_WORK/skills/py-codestyle" \
        "$REPO/.claude/skills/py-codestyle"
    ln -s "$second_source/skills/py-codestyle" \
        "$REPO/.opencode/skills/py-codestyle"
    local before
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'mixed source roots'
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_eq "$(tree_digest "$REPO")" "$before"
    [ ! -e "$REPO/.ai" ] || fail 'mixed-root migration created anchor'

    new_repo partial-migration
    mkdir -p "$REPO/.claude/skills/pr-msg"
    ln -s "$SOURCE_WORK/skills/pr-msg/SKILL.md" \
        "$REPO/.claude/skills/pr-msg/SKILL.md"
    ln -s "$SOURCE_WORK/skills/pr-msg/references" \
        "$REPO/.claude/skills/pr-msg/references"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'missing or unmanaged hybrid migration asset'
    assert_eq "$(tree_digest "$REPO")" "$before"
    [ ! -e "$REPO/.ai" ] || fail 'partial migration created anchor'

    new_repo anchor-parent-conflict
    printf conflict > "$REPO/.ai"
    mkdir -p "$REPO/.claude/skills"
    ln -s "$SOURCE_WORK/skills/py-codestyle" \
        "$REPO/.claude/skills/py-codestyle"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'anchor parent is not a directory'
    assert_eq "$(tree_digest "$REPO")" "$before"
    pass 'migration fully preflights mixed roots and missing assets with zero mutation'
}

test_migration_refreshes_historical_command_copy() {
    local source="$TMP_ROOT/stale-command-source"
    git clone -q "$SOURCE_WORK" "$source"
    git -C "$source" config user.email fixture@example.com
    git -C "$source" config user.name Fixture
    new_repo stale-command-migration
    mkdir -p "$REPO/.ai"
    ln -s "$source" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    local stale_digest dry
    stale_digest="$(file_digest "$REPO/.opencode/commands/commit-msg.md")"
    printf '\nselected-anchor-revision\n' \
        >> "$source/providers/opencode/commands/commit-msg.md"
    git -C "$source" add providers/opencode/commands/commit-msg.md
    git -C "$source" commit -qm 'update command fixture'
    dry="$(bash "$DEPLOY" migrate "$REPO" --dry-run)"
    assert_contains "$dry" \
        'Would refresh managed copy .opencode/commands/commit-msg.md from selected anchor'
    assert_eq "$(file_digest "$REPO/.opencode/commands/commit-msg.md")" "$stale_digest"
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    grep -q selected-anchor-revision "$REPO/.opencode/commands/commit-msg.md" \
        || fail 'migration did not refresh copied command from selected anchor'
    bash "$DEPLOY" status "$REPO" --provider opencode >/dev/null \
        || fail 'status is unhealthy after copied-command refresh'
    pass 'migration refreshes recognized historical command copies from selected anchor'
}

add_legacy_submodule() {
    local repo="$1" url="$2"
    git -c protocol.file.allow=always -C "$repo" submodule add -q "$url" .claude/ai.skillz
    git -C "$repo" add .gitmodules .claude/ai.skillz
    git -C "$repo" commit -qm 'legacy submodule'
}

test_legacy_submodule_relocation() {
    new_repo legacy-submodule
    add_legacy_submodule "$REPO" "$SOURCE_URL"
    mkdir -p "$REPO/.claude/skills/commit-msg/msgs"
    ln -s '../../ai.skillz/skills/commit-msg/SKILL.md' \
        "$REPO/.claude/skills/commit-msg/SKILL.md"
    printf state > "$REPO/.claude/skills/commit-msg/msgs/old.md"
    local url commit index_before before dry real dry_actions real_actions
    url="$(git -C "$REPO" config -f .gitmodules --get-regexp '\.url$' \
        | while read -r _ value; do printf '%s' "$value"; done)"
    commit="$(git -C "$REPO/.claude/ai.skillz" rev-parse HEAD)"
    index_before="$(index_tree "$REPO")"
    before="$(tree_digest "$REPO")"
    dry="$(bash "$DEPLOY" migrate "$REPO" --dry-run)"
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_contains "$dry" 'Would move legacy submodule'
    real="$(bash "$DEPLOY" migrate "$REPO")"
    dry_actions="$(printf '%s\n' "$dry" | while IFS= read -r line; do
        case "$line" in Would\ *) printf '%s\n' "${line#Would }" ;; esac
    done)"
    real_actions="$(printf '%s\n' "$real" | while IFS= read -r line; do
        case "$line" in 'Migration inspection complete;'*) ;; *) printf '%s\n' "$line" ;; esac
    done)"
    assert_eq "$real_actions" "$dry_actions"
    assert_eq "$(index_tree "$REPO")" "$index_before"
    [ ! -e "$REPO/.claude/ai.skillz" ] || fail 'legacy submodule path remains'
    [ -f "$REPO/.ai/ai.skillz/.git" ] || fail 'new submodule path missing'
    assert_eq "$(git -C "$REPO/.ai/ai.skillz" rev-parse HEAD)" "$commit"
    assert_eq "$(git -C "$REPO" config -f .gitmodules --get-regexp '\.url$' \
        | while read -r _ value; do printf '%s' "$value"; done)" "$url"
    assert_eq "$(<"$REPO/.claude/skills/commit-msg/msgs/old.md")" state

    new_repo staged-legacy
    add_legacy_submodule "$REPO" "$SOURCE_URL"
    printf staged > "$REPO/staged.txt"
    git -C "$REPO" add staged.txt
    local staged_before
    staged_before="$(index_entry "$REPO" staged.txt)"
    bash "$DEPLOY" migrate "$REPO" --stage >/dev/null
    assert_eq "$(index_entry "$REPO" staged.txt)" "$staged_before"
    [ -z "$(index_entry "$REPO" .claude/ai.skillz)" ] \
        || fail 'old legacy gitlink remains staged'
    index_entry "$REPO" .ai/ai.skillz | grep -q '^160000 ' \
        || fail 'relocated gitlink was not staged exactly'

    new_repo dirty-legacy
    add_legacy_submodule "$REPO" "$SOURCE_URL"
    printf dirty >> "$REPO/.claude/ai.skillz/README.md"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'dirty legacy submodule'

    local nested_source="$TMP_ROOT/nested-source"
    git clone -q "$SOURCE_WORK" "$nested_source"
    git -C "$nested_source" config user.email fixture@example.com
    git -C "$nested_source" config user.name Fixture
    git -C "$nested_source" update-index --add --cacheinfo \
        "160000,$commit,nested"
    git -C "$nested_source" commit -qm nested
    new_repo nested-legacy
    add_legacy_submodule "$REPO" "file://$nested_source"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'nested gitlinks'
    pass 'clean legacy submodules relocate with URL/commit/index preserved and unsafe cases refuse'
}

test_json_skills_paths_inspection() {
    new_repo json-status
    mkdir -p "$REPO/.opencode"
    printf '{"other":{"paths":["/tmp/not-skills"]},"note":"/tmp/catalog/skills"}\n' \
        > "$REPO/.opencode/opencode.json"
    local output
    output="$(bash "$DEPLOY" status "$REPO")"
    assert_contains "$output" 'portable skills.paths'
    printf '{"skills" : { "paths" : [ "/tmp/path with spaces/skills" ] }}\n' \
        > "$REPO/.opencode/opencode.json"
    assert_fails bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'skills.paths contains absolute path: /tmp/path with spaces/skills'
    rm "$REPO/.opencode/opencode.json"
    printf '{ // comment\n "skills": {"paths": ["/tmp/path with spaces/skills",],}\n}\n' \
        > "$REPO/.opencode/opencode.jsonc"
    assert_fails bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" '/tmp/path with spaces/skills'
    assert_fails env AI_SKILLZ_NO_PYTHON=yes bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" '/tmp/path with spaces/skills'
    printf '{ // comment\n "skills": {"paths": ["skills"]}\n}\n' \
        > "$REPO/.opencode/opencode.jsonc"
    output="$(env AI_SKILLZ_NO_PYTHON=yes bash "$DEPLOY" status "$REPO")"
    assert_contains "$output" 'inspected via fallback'
    printf '{\n "skills": {"metadata": {"nested": true}, "paths": ["/tmp/nested path/skills"]}\n}\n' \
        > "$REPO/.opencode/opencode.jsonc"
    assert_fails env AI_SKILLZ_NO_PYTHON=yes bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'skills.paths inspection uncertain [UNHEALTHY]'
    pass 'status scopes and parses JSON/JSONC skills.paths with fallback support'
}

test_init_option_consistency() {
    new_repo init-options-local
    assert_fails bash "$DEPLOY" init "$REPO" --method symlink --url "$SOURCE_URL"
    [ ! -e "$REPO/.ai/ai.skillz" ] || fail 'invalid local --url mutated target'
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    assert_fails bash "$DEPLOY" init "$REPO" --method symlink --ref HEAD

    new_repo init-options-submodule
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" \
        --ref HEAD >/dev/null
    assert_fails bash "$DEPLOY" init "$REPO" --method submodule --url file:///different
    pass 'existing and new anchors consistently apply or reject --url/--ref combinations'
}

test_managed_command_copy_update() {
    local update_source="$TMP_ROOT/update-source"
    git clone -q "$SOURCE_WORK" "$update_source"
    git -C "$update_source" config user.email fixture@example.com
    git -C "$update_source" config user.name Fixture
    new_repo command-update
    mkdir -p "$REPO/.ai"
    ln -s "$update_source" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    printf '\nmanaged-v2\n' >> "$update_source/providers/opencode/commands/commit-msg.md"
    git -C "$update_source" add providers/opencode/commands/commit-msg.md
    git -C "$update_source" commit -qm v2
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    grep -q managed-v2 "$REPO/.opencode/commands/commit-msg.md" \
        || fail 'recognized historical command copy was not updated'
    pass 'recognized historical command copies update while user files remain protected'
}

test_update_behavior_and_broken_anchor() {
    new_repo local-update
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    assert_contains "$(bash "$DEPLOY" update "$REPO")" \
        'Local symlink anchor already follows'
    rm "$REPO/.ai/ai.skillz"
    ln -s "$REPO/missing" "$REPO/.ai/ai.skillz"
    assert_fails bash "$DEPLOY" status "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" '[broken, UNHEALTHY]'

    new_repo submodule-update
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    local ref index_before
    ref="$(git -C "$REPO/.ai/ai.skillz" rev-parse HEAD)"
    index_before="$(index_tree "$REPO")"
    bash "$DEPLOY" update "$REPO" --ref "$ref" >/dev/null
    assert_eq "$(index_tree "$REPO")" "$index_before"
    printf dirty >> "$REPO/.ai/ai.skillz/README.md"
    assert_fails bash "$DEPLOY" update "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'refusing to update dirty submodule'
    pass 'update behavior preserves index and broken/dirty anchors report unhealthy'
}

test_deployment_validator_failures() {
    "$ROOT/scripts/validate-deployment.sh" "$ROOT" >/dev/null

    new_repo validate-broken-anchor
    mkdir -p "$REPO/.ai"
    ln -s "$REPO/missing" "$REPO/.ai/ai.skillz"
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"

    new_repo validate-absolute-config
    printf '{"skills":{"paths":["/tmp/path with spaces/skills"]}}\n' \
        > "$REPO/opencode.json"
    git -C "$REPO" add opencode.json
    git -C "$REPO" commit -qm 'absolute config fixture'
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'skills.paths contains absolute path'

    new_repo validate-runtime
    mkdir -p "$REPO/.claude"
    printf runtime > "$REPO/.claude/review_regression.md"
    git -C "$REPO" add -f .claude/review_regression.md
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'runtime state is staged'

    new_repo validate-absolute-link
    mkdir -p "$REPO/.opencode/skills"
    ln -s "$ROOT/skills/py-codestyle" "$REPO/.opencode/skills/py-codestyle"
    git -C "$REPO" add .opencode/skills/py-codestyle
    rm "$REPO/.opencode/skills/py-codestyle"
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'committed absolute provider link'

    new_repo validate-tracked-runtime
    mkdir -p "$REPO/.claude/skills/commit-msg/msgs"
    printf tracked > "$REPO/.claude/skills/commit-msg/msgs/tracked.md"
    git -C "$REPO" add .claude/skills/commit-msg/msgs/tracked.md
    git -C "$REPO" commit -qm 'tracked runtime fixture'
    rm "$REPO/.claude/skills/commit-msg/msgs/tracked.md"
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'runtime state is staged or tracked: .claude/skills/commit-msg/msgs/tracked.md'

    new_repo validate-command-dependency
    mkdir -p "$REPO/.opencode/commands"
    cp "$ROOT/providers/opencode/commands/commit-msg.md" \
        "$REPO/.opencode/commands/commit-msg.md"
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'dependency skill commit-msg missing or unhealthy'

    new_repo validate-hybrid
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" pr-msg "$REPO" --provider opencode >/dev/null
    rm "$REPO/.opencode/skills/pr-msg/scripts"
    ln -s '../../../.ai/ai.skillz/skills/pr-msg/missing' \
        "$REPO/.opencode/skills/pr-msg/scripts"
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'broken ->'
    pass 'deployment validator catches anchors, config, runtime state, and hybrid failures'
}

test_all_templates_invalid_args_and_idempotence() {
    new_repo all-and-validation
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    local output before after
    output="$(bash "$DEPLOY" all "$REPO" --provider all)"
    assert_contains "$output" 'Result: 28 deployed, 2 template skipped'
    [ ! -e "$REPO/.claude/skills/run-tests" ] || fail 'template destination created'
    before="$(tree_digest "$REPO")"
    bash "$DEPLOY" all "$REPO" --provider all >/dev/null
    after="$(tree_digest "$REPO")"
    assert_eq "$after" "$before"
    assert_fails bash "$DEPLOY" '../py-codestyle' "$REPO"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider vscode
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --method copy
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider
    pass 'all skips templates, remains idempotent, and validates names/options strictly'
}

test_opencode_debug_if_available() {
    if ! command -v opencode >/dev/null 2>&1; then
        pass 'OpenCode debug validation skipped (opencode unavailable)'
        return 0
    fi
    new_repo opencode-debug
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    local config_output="$TMP_ROOT/opencode-config.out"
    local skill_output="$TMP_ROOT/opencode-skill.out"
    (cd "$REPO" && opencode debug config > "$config_output")
    (cd "$REPO" && opencode debug skill > "$skill_output")
    assert_file_contains "$config_output" '"commit-msg"'
    assert_file_contains "$skill_output" '"name": "commit-msg"'
    assert_file_contains "$skill_output" \
        "\"location\": \"$REPO/.opencode/skills/commit-msg/SKILL.md\""
    pass 'OpenCode debug config and skill resolve deployed fixture'
}

prepare_source_repo
test_local_anchor_and_anchor_authority
test_subdirectory_resolves_repository_root
test_submodule_and_portable_default_url
test_init_stage_preserves_gitmodules_index
test_phase0_and_global_compatibility
test_exact_staging_and_index_preservation
test_managed_replacement_safety
test_provider_all_skill_preflight
test_external_gitignore_symlink_refusal
test_external_provider_parent_refusal
test_direct_opencode_with_existing_claude_and_config
test_missing_anchor_assets_and_command_preflight
test_runtime_ignores_and_state_preservation
test_command_dependency_all_and_hooks
test_status_health_templates_and_source_symlink
test_gitignore_integrity_and_inventory
test_direct_migration_dry_run
test_migration_full_preflight_zero_mutation
test_migration_refreshes_historical_command_copy
test_legacy_submodule_relocation
test_json_skills_paths_inspection
test_init_option_consistency
test_managed_command_copy_update
test_update_behavior_and_broken_anchor
test_deployment_validator_failures
test_all_templates_invalid_args_and_idempotence
test_opencode_debug_if_available

printf '1..%d\n' "$PASS"
