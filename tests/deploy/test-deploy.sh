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
    cp "$ROOT/providers/opencode/commands/"*.md \
        "$SOURCE_WORK/providers/opencode/commands/"
    cp "$ROOT/skills/run-tests/SKILL.md" \
        "$SOURCE_WORK/skills/run-tests/SKILL.md"
    cp -R "$ROOT/skills/code-review" "$SOURCE_WORK/skills/"
    cp -R "$ROOT/skills/gish" "$SOURCE_WORK/skills/"
    cp -R "$ROOT/skills/harness-perf" "$SOURCE_WORK/skills/"
    cp "$ROOT/deploy-manifest.conf" "$SOURCE_WORK/deploy-manifest.conf"
    cp "$ROOT/gitignore-patterns.conf" "$SOURCE_WORK/gitignore-patterns.conf"
    cp "$ROOT/.gitignore" "$SOURCE_WORK/.gitignore"
    cp "$ROOT/scripts/deploy.sh" "$SOURCE_WORK/scripts/deploy.sh"
    cp "$ROOT/scripts/validate-deployment.sh" \
        "$SOURCE_WORK/scripts/validate-deployment.sh"
    chmod +x "$SOURCE_WORK/scripts/deploy.sh" \
        "$SOURCE_WORK/scripts/validate-deployment.sh"
    mkdir -p "$SOURCE_WORK/.opencode/commands"
    for command in code-review code-review-changes commit-msg run-tests taken-export; do
        rm -f "$SOURCE_WORK/.opencode/commands/$command.md"
        ln -s "../../providers/opencode/commands/$command.md" \
            "$SOURCE_WORK/.opencode/commands/$command.md"
    done
    git -C "$SOURCE_WORK" add .gitignore deploy-manifest.conf gitignore-patterns.conf \
        scripts/deploy.sh scripts/validate-deployment.sh \
        providers/opencode/commands skills/code-review skills/gish \
        skills/harness-perf \
        skills/run-tests/SKILL.md \
        .opencode/commands
    git -C "$SOURCE_WORK" commit --allow-empty -qm 'fixture deployment source'
    SOURCE_URL="file://$SOURCE_WORK"
}

test_local_anchor_and_anchor_authority() {
    new_repo local-anchor
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/py-codestyle")" \
        "$ROOT/skills/py-codestyle"
    assert_eq "$(readlink "$REPO/.opencode/skills/py-codestyle")" \
        "$ROOT/skills/py-codestyle"

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

test_submodule_and_default_url() {
    new_repo submodule
    local before
    before="$(index_tree "$REPO")"
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    assert_eq "$(index_tree "$REPO")" "$before"
    bash "$DEPLOY" py-codestyle "$REPO" --provider all >/dev/null
    assert_eq "$(readlink "$REPO/.opencode/skills/py-codestyle")" \
        '../../.ai/ai.skillz/skills/py-codestyle'

    assert_contains "$(bash "$DEPLOY" --help)" \
        'https://github.com/baudco/ai.skillz.git'
    pass 'submodule deployment is unstaged and advertises the canonical default URL'
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

test_submodule_init_boundaries() {
    new_repo external-gitmodules
    local external="$TMP_ROOT/external-gitmodules-file" before tree_before
    printf 'external-user-content\n' > "$external"
    ln -s "$external" "$REPO/.gitmodules"
    before="$(file_digest "$external")"
    tree_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" init "$REPO" --method submodule \
        --url "$SOURCE_URL"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'refusing symlinked .gitmodules'
    assert_eq "$(file_digest "$external")" "$before"
    assert_eq "$(tree_digest "$REPO")" "$tree_before"
    [ ! -e "$REPO/.ai" ] || fail 'unsafe .gitmodules preflight created anchor state'

    new_repo invalid-new-submodule-ref
    tree_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" init "$REPO" --method submodule \
        --url "$SOURCE_URL" --ref no-such-ref
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'submodule ref not found'
    assert_eq "$(tree_digest "$REPO")" "$tree_before"
    [ ! -e "$REPO/.gitmodules" ] \
        || fail 'failed ref left .gitmodules behind'
    [ ! -e "$REPO/.ai" ] || fail 'failed ref left anchor state behind'

    new_repo initialized-submodule-source
    git -c protocol.file.allow=always -C "$REPO" submodule add -q \
        "$SOURCE_URL" .ai/ai.skillz
    git -C "$REPO" commit -qam 'portable fixture'
    local portable_source="$REPO"
    local invalid_clone="$TMP_ROOT/uninitialized-invalid-ref"
    git clone -q "$portable_source" "$invalid_clone"
    REPO="$invalid_clone"
    local submodule_key submodule_name modules_path
    submodule_key="$(git -C "$REPO" config -f .gitmodules \
        --get-regexp '^submodule\..*\.path$' | while read -r key _; do
            printf '%s' "$key"
        done)"
    submodule_name="${submodule_key#submodule.}"
    submodule_name="${submodule_name%.path}"
    modules_path="$(git -C "$REPO" rev-parse --git-path "modules/$submodule_name")"
    case "$modules_path" in /*) ;; *) modules_path="$REPO/$modules_path" ;; esac
    [ ! -e "$modules_path" ] || fail 'fixture module repository already exists'
    assert_fails bash "$DEPLOY" init "$REPO" --method submodule \
        --ref no-such-ref
    [ ! -f "$REPO/.ai/ai.skillz/.git" ] \
        || fail 'failed ref left registered submodule initialized'
    [ ! -e "$modules_path" ] \
        || fail 'failed ref left cloned module repository metadata'

    local clone="$TMP_ROOT/uninitialized-submodule-clone"
    git clone -q "$portable_source" "$clone"
    REPO="$clone"
    [ ! -f "$REPO/.ai/ai.skillz/.git" ] \
        || fail 'fixture submodule initialized unexpectedly'
    bash "$DEPLOY" init "$REPO" --method submodule >/dev/null
    [ -f "$REPO/.ai/ai.skillz/.git" ] \
        || fail 'registered submodule was not initialized'
    bash "$DEPLOY" status "$REPO" --provider all >/dev/null
    pass 'submodule init refuses unsafe metadata and initializes registered gitlinks'
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

test_global_skill_deployment_safety() {
    local home="$TMP_ROOT/global-skill-home"
    mkdir -p "$home/.claude/skills"
    cp -a "$ROOT/skills/py-codestyle" "$home/.claude/skills/py-codestyle"
    HOME="$home" bash "$DEPLOY" py-codestyle --global >/dev/null
    assert_eq "$(readlink "$home/.claude/skills/py-codestyle")" \
        "$ROOT/skills/py-codestyle"
    compgen -G "$home/.claude/skills/.ai-skillz-link.*" >/dev/null \
        && fail 'global canonical-copy replacement left swap state'
    local before
    before="$(tree_digest "$home")"
    HOME="$home" bash "$DEPLOY" py-codestyle --global >/dev/null
    assert_eq "$(tree_digest "$home")" "$before"

    home="$TMP_ROOT/global-cleanup-failure-home"
    mkdir -p "$home/.claude/skills"
    cp -a "$ROOT/skills/gish" "$home/.claude/skills/gish"
    chmod u-w "$home/.claude/skills/gish/references"
    assert_fails env HOME="$home" bash "$DEPLOY" gish --global
    [ -L "$home/.claude/skills/gish" ] \
        || fail 'cleanup failure did not leave the canonical global link installed'
    local swaps=("$home/.claude/skills"/.ai-skillz-link.*)
    [ ${#swaps[@]} -eq 1 ] && [ -d "${swaps[0]}/original" ] \
        || fail 'cleanup failure did not retain exactly one source-copy backup'
    chmod -R u+w "${swaps[0]}"
    rm -rf "${swaps[0]}"

    home="$TMP_ROOT/global-canonical-parent-home"
    mkdir -p "$home/.claude"
    ln -s "$ROOT/skills" "$home/.claude/skills"
    HOME="$home" bash "$DEPLOY" commit-msg --global >/dev/null
    assert_eq "$(readlink "$home/.claude/skills")" "$ROOT/skills"

    home="$TMP_ROOT/global-hybrid-home"
    mkdir -p "$home/.claude/skills/run-tests"
    cp "$ROOT/skills/run-tests/SKILL.md" \
        "$home/.claude/skills/run-tests/SKILL.md"
    printf 'local harness\n' \
        > "$home/.claude/skills/run-tests/test-harness-reference.md"
    HOME="$home" bash "$DEPLOY" run-tests --global --provider all >/dev/null
    assert_eq "$(readlink "$home/.claude/skills/run-tests/SKILL.md")" \
        "$ROOT/skills/run-tests/SKILL.md"
    assert_eq "$(<"$home/.claude/skills/run-tests/test-harness-reference.md")" \
        'local harness'
    [ ! -e "$home/.opencode" ] \
        || fail 'global provider all unexpectedly created an OpenCode destination'

    mkdir -p "$home/.claude/skills/pr-msg"
    cp "$ROOT/skills/pr-msg/SKILL.md" "$home/.claude/skills/pr-msg/SKILL.md"
    cp -a "$ROOT/skills/pr-msg/references" "$home/.claude/skills/pr-msg/references"
    cp -a "$ROOT/skills/pr-msg/scripts" "$home/.claude/skills/pr-msg/scripts"
    printf 'local pr state\n' > "$home/.claude/skills/pr-msg/pr-merge.xsh"
    HOME="$home" bash "$DEPLOY" pr-msg --global >/dev/null
    assert_eq "$(readlink "$home/.claude/skills/pr-msg/SKILL.md")" \
        "$ROOT/skills/pr-msg/SKILL.md"
    assert_eq "$(readlink "$home/.claude/skills/pr-msg/references")" \
        "$ROOT/skills/pr-msg/references"
    assert_eq "$(readlink "$home/.claude/skills/pr-msg/scripts")" \
        "$ROOT/skills/pr-msg/scripts"
    assert_eq "$(<"$home/.claude/skills/pr-msg/pr-merge.xsh")" 'local pr state'

    home="$TMP_ROOT/global-nested-link-home"
    local external_asset="$TMP_ROOT/global-hybrid-external"
    local nested_source="$TMP_ROOT/global-nested-source"
    git clone -q "$SOURCE_WORK" "$nested_source"
    mkdir -p "$nested_source/skills/run-tests/references"
    cp "$ROOT/skills/run-tests/references/tractor-example.md" \
        "$nested_source/skills/run-tests/references/tractor-example.md"
    sed -i \
        's#^skill|run-tests|hybrid|SKILL.md$#skill|run-tests|hybrid|SKILL.md,references/tractor-example.md#' \
        "$nested_source/deploy-manifest.conf"
    mkdir -p "$home/.claude/skills/run-tests" "$external_asset"
    cp "$nested_source/skills/run-tests/SKILL.md" \
        "$home/.claude/skills/run-tests/SKILL.md"
    printf 'external\n' > "$external_asset/user.txt"
    ln -s "$external_asset" "$home/.claude/skills/run-tests/references"
    before="$(tree_digest "$external_asset")"
    local home_before="$(tree_digest "$home")"
    assert_fails env HOME="$home" bash \
        "$nested_source/scripts/deploy.sh" run-tests --global
    assert_eq "$(tree_digest "$external_asset")" "$before"
    assert_eq "$(tree_digest "$home")" "$home_before"

    home="$TMP_ROOT/global-unmanaged-home"
    mkdir -p "$home/.claude/skills/py-codestyle"
    printf 'user-owned\n' > "$home/.claude/skills/py-codestyle/user.txt"
    before="$(tree_digest "$home")"
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle --global
    assert_eq "$(tree_digest "$home")" "$before"

    home="$TMP_ROOT/global-parent-link-home"
    local external="$TMP_ROOT/global-parent-external"
    mkdir -p "$home/.claude" "$external"
    printf 'external\n' > "$external/user.txt"
    ln -s "$external" "$home/.claude/skills"
    before="$(tree_digest "$external")"
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle --global
    assert_eq "$(tree_digest "$external")" "$before"

    new_repo global-skill-args
    home="$TMP_ROOT/global-args-home"
    mkdir -p "$home"
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle "$REPO" --global
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle --global \
        --provider opencode
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle --global --stage
    assert_fails env HOME="$home" bash "$DEPLOY" py-codestyle --global \
        --method submodule
    pass 'global skills convert canonical copies and refuse unsafe destinations/options'
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
    [ -z "$(index_entry "$REPO" .claude/skills/commit-msg/SKILL.md)" ] \
        || fail 'local-only canonical hybrid link was staged'
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

    new_repo recognized-command-copy
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    mkdir -p "$REPO/.opencode/commands"
    cp "$ROOT/providers/opencode/commands/commit-msg.md" \
        "$REPO/.opencode/commands/commit-msg.md"
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    [ -L "$REPO/.opencode/commands/commit-msg.md" ] \
        || fail 'recognized canonical command copy was not converted to a link'

    local history_source="$TMP_ROOT/historical-command-source"
    local historical_copy="$TMP_ROOT/historical-command.md"
    git clone -q "$SOURCE_WORK" "$history_source"
    git -C "$history_source" config user.email fixture@example.com
    git -C "$history_source" config user.name Fixture
    cp "$history_source/providers/opencode/commands/commit-msg.md" \
        "$historical_copy"
    printf '\nnew canonical revision\n' \
        >> "$history_source/providers/opencode/commands/commit-msg.md"
    git -C "$history_source" add providers/opencode/commands/commit-msg.md
    git -C "$history_source" commit -qm 'update command history fixture'
    new_repo historical-command-copy
    mkdir -p "$REPO/.ai"
    ln -s "$history_source" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    mkdir -p "$REPO/.opencode/commands"
    cp "$historical_copy" "$REPO/.opencode/commands/commit-msg.md"
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    [ -L "$REPO/.opencode/commands/commit-msg.md" ] \
        || fail 'historical canonical command copy was not converted to a link'

    new_repo recognized-transition
    bash "$DEPLOY" py-codestyle "$REPO" >/dev/null
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" py-codestyle "$REPO" >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/py-codestyle")" \
        "$ROOT/skills/py-codestyle"
    pass 'only positively recognized provider links are replaceable'
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

    new_repo internal-provider-parent
    mkdir -p "$REPO/config/claude"
    ln -s config/claude "$REPO/.claude"
    target_before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" commit-msg "$REPO" --provider claude
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'refusing symlinked provider parent'
    assert_eq "$(tree_digest "$REPO")" "$target_before"
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
    bash "$DEPLOY" all "$REPO" --provider opencode >/dev/null
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
    printf '!/.claude/skills/commit-msg/msgs/\n' >> "$REPO/.gitignore"
    assert_fails bash "$DEPLOY" commit-msg "$REPO" --provider opencode
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'would not be effectively ignored'
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'UNHEALTHY:not ignored'

    new_repo runtime-through-legacy-link
    local legacy_skill="$TMP_ROOT/runtime-legacy-commit-msg"
    mkdir -p "$legacy_skill" "$REPO/.claude/skills"
    ln -s "$legacy_skill" "$REPO/.claude/skills/commit-msg"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    local output
    output="$(bash "$DEPLOY" status "$REPO" --provider opencode 2>&1)"
    assert_not_contains "$output" 'beyond a symbolic link'
    assert_not_contains "$output" 'UNHEALTHY:not ignored'

    new_repo code-review-runtime
    bash "$DEPLOY" code-review "$REPO" --provider opencode >/dev/null
    assert_file_contains "$REPO/.gitignore" '.ai/code-review/reports/'
    mkdir -p "$REPO/.ai/code-review/reports"
    printf report > "$REPO/.ai/code-review/reports/result.json"
    git -C "$REPO" check-ignore -q -- \
        .ai/code-review/reports/result.json \
        || fail 'code-review report is not ignored'
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

    new_repo run-tests-status
    bash "$DEPLOY" run-tests "$REPO" --provider claude --method symlink \
        >/dev/null
    local harness="$REPO/.claude/skills/run-tests/test-harness-reference.md"
    printf 'consumer-owned harness\n' > "$harness"
    local harness_before
    harness_before="$(file_digest "$harness")"
    bash "$DEPLOY" run-tests "$REPO" --provider claude --method symlink \
        >/dev/null
    assert_eq "$(file_digest "$harness")" "$harness_before"
    assert_contains "$(bash "$DEPLOY" status "$REPO" --provider claude)" \
        'skill run-tests                SKILL.md: local-only (absolute)'

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
    local source_link
    source_link="$(readlink "$source_repo/.opencode/commands/commit-msg.md")"
    bash "$source_repo/scripts/deploy.sh" command all "$source_repo" \
        --provider opencode --method symlink >/dev/null
    assert_eq "$(readlink "$source_repo/.opencode/commands/commit-msg.md")" \
        "$source_link"
    git -C "$source_repo" diff --quiet -- .opencode/commands \
        || fail 'source-repository command deployment rewrote tracked links'
    git -C "$source_repo" check-ignore -q --no-index -- \
        .opencode/commands/commit-msg.md \
        && fail 'source-repository command deployment ignored tracked link'
    local source_status
    source_status="$(bash "$source_repo/scripts/deploy.sh" status "$source_repo")"
    assert_contains "$source_status" 'runtime-state-only (not deployed) [healthy]'
    assert_contains "$source_status" 'intentional source-repo symlink [healthy]'
    "$source_repo/scripts/validate-deployment.sh" "$source_repo" >/dev/null
    ln -s "$source_repo/skills/commit-msg/missing" \
        "$source_repo/.claude/skills/commit-msg/SKILL.md"
    assert_fails bash "$source_repo/scripts/deploy.sh" status "$source_repo"
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'broken ->'
    pass 'status catches broken links and accepts hybrid/source-repo command links'
}

test_run_tests_hybrid_migration_safety() {
    local legacy_root="$TMP_ROOT/legacy-ai-skillz"
    local legacy_source legacy_before
    git clone -q "$SOURCE_WORK" "$legacy_root"
    legacy_source="$legacy_root/skills/run-tests"
    legacy_before="$(file_digest "$legacy_source/SKILL.md")"

    new_repo run-tests-legacy-link
    mkdir -p "$REPO/.claude/skills"
    ln -s "$legacy_source" "$REPO/.claude/skills/run-tests"
    bash "$DEPLOY" run-tests "$REPO" --provider claude --method symlink \
        >/dev/null
    [ ! -L "$REPO/.claude/skills/run-tests" ] \
        || fail 'legacy run-tests directory link was not replaced'
    assert_eq "$(file_digest "$legacy_source/SKILL.md")" "$legacy_before"
    [ -L "$REPO/.claude/skills/run-tests/SKILL.md" ] \
        || fail 'canonical run-tests SKILL.md link was not installed'

    new_repo run-tests-local-skill
    mkdir -p "$REPO/.claude/skills/run-tests"
    printf 'project-owned skill\n' > "$REPO/.claude/skills/run-tests/SKILL.md"
    assert_fails bash "$DEPLOY" run-tests "$REPO" --provider claude \
        --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'local run-tests/SKILL.md exists'

    new_repo run-tests-directory-harness
    mkdir -p \
        "$REPO/.claude/skills/run-tests/test-harness-reference.md"
    assert_fails bash "$DEPLOY" run-tests "$REPO" --provider claude \
        --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'test-harness-reference.md must be a regular local file'
    [ ! -e "$REPO/.claude/skills/run-tests/SKILL.md" ] \
        || fail 'directory harness was mutated before rejection'

    new_repo run-tests-linked-harness
    local linked_harness="$TMP_ROOT/linked-harness.md"
    mkdir -p "$REPO/.claude/skills/run-tests"
    printf 'external harness\n' > "$linked_harness"
    ln -s "$linked_harness" \
        "$REPO/.claude/skills/run-tests/test-harness-reference.md"
    assert_fails bash "$DEPLOY" run-tests "$REPO" --provider claude \
        --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'test-harness-reference.md must be a regular local file'
    [ ! -e "$REPO/.claude/skills/run-tests/SKILL.md" ] \
        || fail 'linked harness was mutated before rejection'

    new_repo run-tests-unrecognized-link
    local arbitrary="$TMP_ROOT/user-integration/.claude/skills/run-tests"
    mkdir -p "$arbitrary" "$REPO/.claude/skills"
    printf '%s\n' '---' 'name: run-tests' '---' > "$arbitrary/SKILL.md"
    ln -s "$arbitrary" "$REPO/.claude/skills/run-tests"
    assert_fails bash "$DEPLOY" run-tests "$REPO" --provider claude \
        --method symlink
    [ -L "$REPO/.claude/skills/run-tests" ] \
        || fail 'unrecognized run-tests directory link was removed'

    new_repo run-tests-unrelated-git-link
    local unrelated_git="$TMP_ROOT/unrelated-run-tests-repo"
    mkdir -p "$unrelated_git/skills/run-tests" "$REPO/.claude/skills"
    git -C "$unrelated_git" init -q
    printf '%s\n' '---' 'name: run-tests' '---' \
        > "$unrelated_git/skills/run-tests/SKILL.md"
    ln -s "$unrelated_git/skills/run-tests" \
        "$REPO/.claude/skills/run-tests"
    assert_fails bash "$DEPLOY" run-tests "$REPO" --provider claude \
        --method symlink
    [ -L "$REPO/.claude/skills/run-tests" ] \
        || fail 'unrelated Git run-tests directory link was removed'

    new_repo run-tests-command
    bash "$DEPLOY" run-tests "$REPO" --provider opencode --method symlink \
        >/dev/null
    bash "$DEPLOY" command run-tests "$REPO" --provider opencode \
        --method symlink >/dev/null
    assert_eq "$(readlink "$REPO/.opencode/commands/run-tests.md")" \
        "$ROOT/providers/opencode/commands/run-tests.md"
    git -C "$REPO" check-ignore -q -- .opencode/commands/run-tests.md \
        || fail 'local run-tests command link was not ignored'
    mkdir -p "$REPO/.claude/skills/run-tests"
    printf 'OpenCode-only harness\n' \
        > "$REPO/.claude/skills/run-tests/test-harness-reference.md"
    local output
    output="$(bash "$DEPLOY" status "$REPO" --provider all)"
    assert_contains "$output" 'runtime-state-only (not deployed) [healthy]'
    "$ROOT/scripts/validate-deployment.sh" "$REPO" >/dev/null
    pass 'run-tests hybrid migration preserves local state and rejects project-owned bases'
}

test_local_tracking_and_portable_ignore_preflight() {
    new_repo tracked-local-link
    mkdir -p "$REPO/.opencode/skills"
    ln -s "$ROOT/skills/taken-export" "$REPO/.opencode/skills/taken-export"
    git -C "$REPO" add .opencode/skills/taken-export
    assert_fails bash "$DEPLOY" taken-export "$REPO" --provider opencode \
        --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'local provider destination is tracked'

    new_repo ignored-portable-link
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    printf '/.opencode/skills/\n' >> "$REPO/.gitignore"
    assert_fails bash "$DEPLOY" taken-export "$REPO" --provider opencode \
        --method submodule
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'portable provider destination is ignored'
    [ ! -e "$REPO/.opencode/skills/taken-export" ] \
        || fail 'ignored portable destination was created'

    mkdir -p "$REPO/.opencode/skills"
    ln -s '../../.ai/ai.skillz/skills/taken-export' \
        "$REPO/.opencode/skills/taken-export"
    assert_fails bash "$DEPLOY" status "$REPO" --provider opencode
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'portable link ignored'

    new_repo tracked-local-migration
    mkdir -p "$REPO/.opencode/skills"
    ln -s "$ROOT/skills/taken-export" "$REPO/.opencode/skills/taken-export"
    git -C "$REPO" add .opencode/skills/taken-export
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'local provider destination is tracked'

    new_repo ignored-portable-migration
    bash "$DEPLOY" taken-export "$REPO" --provider opencode \
        --method symlink >/dev/null
    printf '/skills/\n' > "$REPO/.opencode/.gitignore"
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    local before
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'portable provider destination is ignored outside its managed block'
    assert_eq "$(tree_digest "$REPO")" "$before"
    pass 'local tracked links and ignored portable links are rejected before mutation'
}

test_gitignore_integrity_and_inventory() {
    new_repo symlinked-ignore
    mkdir -p "$REPO/config"
    printf 'user-line\n' > "$REPO/config/ignore"
    chmod 640 "$REPO/config/ignore"
    ln -s config/ignore "$REPO/.gitignore"
    local mode_before before
    mode_before="$(mode_string "$REPO/config/ignore")"
    before="$(file_digest "$REPO/config/ignore")"
    assert_fails bash "$DEPLOY" init "$REPO" --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'Git does not follow it'
    [ -L "$REPO/.gitignore" ] || fail '.gitignore symlink was replaced'
    assert_eq "$(mode_string "$REPO/config/ignore")" "$mode_before"
    assert_eq "$(file_digest "$REPO/config/ignore")" "$before"

    new_repo hardlinked-ignore
    local external="$TMP_ROOT/external-hardlinked-ignore"
    printf 'external-user-line\n' > "$external"
    ln "$external" "$REPO/.gitignore"
    before="$(file_digest "$external")"
    bash "$DEPLOY" py-codestyle "$REPO" --method symlink >/dev/null
    assert_eq "$(file_digest "$external")" "$before"
    [ ! "$REPO/.gitignore" -ef "$external" ] \
        || fail '.gitignore still shares an external hard-linked inode'

    new_repo ignore-integrity
    printf 'user-line\n' > "$REPO/.gitignore"
    chmod 640 "$REPO/.gitignore"
    mode_before="$(mode_string "$REPO/.gitignore")"
    bash "$DEPLOY" py-codestyle "$REPO" --method symlink >/dev/null
    printf '!/.claude/skills/py-codestyle\n' >> "$REPO/.gitignore"
    rm "$REPO/.claude/skills/py-codestyle"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --method symlink
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'managed local path would not be effectively ignored'
    assert_eq "$(tree_digest "$REPO")" "$before"
    printf 'user-line\n' > "$REPO/.gitignore"
    bash "$DEPLOY" py-codestyle "$REPO" --method symlink >/dev/null
    git -C "$REPO" check-ignore -q --no-index -- \
        .claude/skills/py-codestyle \
        || fail 'managed ignore block was not effective after correction'
    assert_eq "$(mode_string "$REPO/.gitignore")" "$mode_before"
    assert_file_contains "$REPO/.gitignore" user-line
    bash "$DEPLOY" gitignore "$REPO" >/dev/null
    assert_file_contains "$REPO/.gitignore" '.claude/.current_session'
    assert_file_contains "$REPO/.gitignore" '.claude/skills/commit-msg/msgs/'
    assert_file_contains "$REPO/.gitignore" '.claude/review_regression.md'

    printf '\n# END ai.skillz: bad\n' >> "$REPO/.gitignore"
    before="$(file_digest "$REPO/.gitignore")"
    assert_fails bash "$DEPLOY" gitignore "$REPO"
    assert_eq "$(file_digest "$REPO/.gitignore")" "$before"

    new_repo bulk-ignore-preflight
    printf '%s\n' \
        '# BEGIN ai.skillz: runtime:taken-export' \
        '.ai/taken/exports/' \
        '# END ai.skillz: runtime:taken-export' \
        '!/.ai/taken/exports/' > "$REPO/.gitignore"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" gitignore "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'would not be effectively ignored'
    assert_eq "$(tree_digest "$REPO")" "$before"
    pass 'gitignore updates reject symlinks, preserve user content, and remain effective'
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
        "$ROOT/skills/commit-msg/SKILL.md"

    new_repo migration-ignore-preflight
    bash "$DEPLOY" py-codestyle "$REPO" --method symlink >/dev/null
    printf '!/.claude/skills/py-codestyle\n' >> "$REPO/.gitignore"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'would not be effectively ignored'
    assert_eq "$(tree_digest "$REPO")" "$before"
    [ ! -e "$REPO/.ai" ] \
        || fail 'failed migration ignore preflight created an anchor'
    pass 'direct migration dry-run exactly predicts real actions without mutation'
}

test_multi_asset_migration_ignore() {
    new_repo multi-asset-migration
    mkdir -p "$REPO/.claude/skills/pr-msg"
    local asset
    for asset in SKILL.md references scripts; do
        ln -s "$SOURCE_WORK/skills/pr-msg/$asset" \
            "$REPO/.claude/skills/pr-msg/$asset"
    done
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    for asset in SKILL.md references scripts; do
        git -C "$REPO" check-ignore -q --no-index -- \
            ".claude/skills/pr-msg/$asset" \
            || fail "migrated pr-msg asset is not ignored: $asset"
    done
    bash "$DEPLOY" status "$REPO" --provider all >/dev/null

    new_repo partial-multi-asset-ignore
    mkdir -p "$REPO/.claude/skills/pr-msg"
    for asset in SKILL.md references scripts; do
        ln -s "$SOURCE_WORK/skills/pr-msg/$asset" \
            "$REPO/.claude/skills/pr-msg/$asset"
    done
    printf '%s\n' \
        '# BEGIN ai.skillz: direct:symlink:claude:pr-msg' \
        '/.claude/skills/pr-msg/SKILL.md' \
        '# END ai.skillz: direct:symlink:claude:pr-msg' > "$REPO/.gitignore"
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    for asset in SKILL.md references scripts; do
        git -C "$REPO" check-ignore -q --no-index -- \
            ".claude/skills/pr-msg/$asset" \
            || fail "partially migrated pr-msg asset is not ignored: $asset"
    done
    bash "$DEPLOY" status "$REPO" --provider all >/dev/null
    pass 'multi-asset hybrid migration preserves complete ignore coverage'
}

test_direct_to_submodule_migration() {
    new_repo direct-to-submodule
    bash "$DEPLOY" taken-export "$REPO" --provider all --method symlink \
        >/dev/null
    bash "$DEPLOY" command taken-export "$REPO" --provider opencode \
        --method symlink >/dev/null
    rm "$REPO/.opencode/commands/taken-export.md"
    cp "$ROOT/providers/opencode/commands/taken-export.md" \
        "$REPO/.opencode/commands/taken-export.md"
    bash "$DEPLOY" run-tests "$REPO" --provider claude --method symlink \
        >/dev/null
    local harness="$REPO/.claude/skills/run-tests/test-harness-reference.md"
    printf 'portable migration harness\n' > "$harness"
    local harness_before
    harness_before="$(file_digest "$harness")"
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" \
        >/dev/null

    local before dry
    before="$(tree_digest "$REPO")"
    dry="$(bash "$DEPLOY" migrate "$REPO" --dry-run)"
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_contains "$dry" \
        'Would relink .opencode/commands/taken-export.md -> ../../.ai/ai.skillz/providers/opencode/commands/taken-export.md'
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    assert_eq "$(readlink "$REPO/.claude/skills/taken-export")" \
        '../../.ai/ai.skillz/skills/taken-export'
    assert_eq "$(readlink "$REPO/.opencode/commands/taken-export.md")" \
        '../../.ai/ai.skillz/providers/opencode/commands/taken-export.md'
    assert_eq "$(file_digest "$harness")" "$harness_before"
    assert_eq "$(readlink "$REPO/.claude/skills/run-tests/SKILL.md")" \
        '../../../.ai/ai.skillz/skills/run-tests/SKILL.md'
    git -C "$REPO" check-ignore -q -- .opencode/commands/taken-export.md \
        && fail 'migrated portable command link remains ignored'
    bash "$DEPLOY" status "$REPO" --provider all >/dev/null \
        || fail 'direct-to-submodule migration produced unhealthy status'
    pass 'one recognized direct source migrates to an initialized portable submodule'
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
    assert_fails bash "$DEPLOY" status "$REPO" --provider all
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'mixed source roots'
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'mixed source roots'
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_eq "$(tree_digest "$REPO")" "$before"
    [ ! -e "$REPO/.ai" ] || fail 'mixed-root migration created anchor'

    local relative_one="$TMP_ROOT/relative-one-ai.skillz"
    local relative_two="$TMP_ROOT/relative-two-ai.skillz"
    git clone -q "$SOURCE_WORK" "$relative_one"
    git clone -q "$SOURCE_WORK" "$relative_two"
    new_repo mixed-relative-status
    mkdir -p "$REPO/.claude/skills" "$REPO/.opencode/skills"
    ln -s "$(realpath --relative-to="$REPO/.claude/skills" \
        "$relative_one/skills/py-codestyle")" \
        "$REPO/.claude/skills/py-codestyle"
    ln -s "$(realpath --relative-to="$REPO/.opencode/skills" \
        "$relative_two/skills/py-codestyle")" \
        "$REPO/.opencode/skills/py-codestyle"
    assert_fails bash "$DEPLOY" status "$REPO" --provider all
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'mixed source roots'

    new_repo unrelated-git-migration
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" \
        >/dev/null
    local unrelated="$TMP_ROOT/unrelated-skill-repo"
    mkdir -p "$unrelated/skills/py-codestyle" "$REPO/.opencode/skills"
    git -C "$unrelated" init -q
    printf 'skill|py-codestyle|template|-\n' \
        > "$unrelated/deploy-manifest.conf"
    printf '%s\n' '---' 'name: py-codestyle' '---' \
        > "$unrelated/skills/py-codestyle/SKILL.md"
    ln -s "$unrelated/skills/py-codestyle" \
        "$REPO/.opencode/skills/py-codestyle"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'unrecognized or broken migration link'
    assert_eq "$(tree_digest "$REPO")" "$before"
    assert_fails bash "$DEPLOY" migrate "$REPO"
    assert_eq "$(tree_digest "$REPO")" "$before"

    new_repo mixed-submodule-migration
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" \
        >/dev/null
    mkdir -p "$REPO/.claude/skills" "$REPO/.opencode/skills"
    ln -s "$SOURCE_WORK/skills/py-codestyle" \
        "$REPO/.claude/skills/py-codestyle"
    ln -s "$second_source/skills/py-codestyle" \
        "$REPO/.opencode/skills/py-codestyle"
    before="$(tree_digest "$REPO")"
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" 'mixed source roots'
    assert_eq "$(tree_digest "$REPO")" "$before"

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

test_tracked_command_copy_transition() {
    new_repo tracked-command-copy
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode \
        --method symlink >/dev/null
    mkdir -p "$REPO/.opencode/commands"
    cp "$ROOT/providers/opencode/commands/commit-msg.md" \
        "$REPO/.opencode/commands/commit-msg.md"
    git -C "$REPO" add -f .opencode/commands/commit-msg.md
    git -C "$REPO" commit -qm 'tracked command copy fixture'
    assert_fails bash "$DEPLOY" migrate "$REPO" --dry-run
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'tracked canonical command copy must be untracked'
    git -C "$REPO" rm --cached -q -- .opencode/commands/commit-msg.md
    bash "$DEPLOY" migrate "$REPO" --dry-run >/dev/null
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    [ -L "$REPO/.opencode/commands/commit-msg.md" ] \
        || fail 'untracked canonical command copy was not converted to a link'
    pass 'tracked canonical command copies require an explicit index transition'
}

test_migration_preserves_managed_command_link() {
    local source="$TMP_ROOT/managed-command-source"
    git clone -q "$SOURCE_WORK" "$source"
    git -C "$source" config user.email fixture@example.com
    git -C "$source" config user.name Fixture
    new_repo managed-command-migration
    mkdir -p "$REPO/.ai"
    ln -s "$source" "$REPO/.ai/ai.skillz"
    printf '/.ai/ai.skillz\n' > "$REPO/.gitignore"
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    local initial_digest dry
    initial_digest="$(file_digest "$REPO/.opencode/commands/commit-msg.md")"
    printf '\nselected-anchor-revision\n' \
        >> "$source/providers/opencode/commands/commit-msg.md"
    git -C "$source" add providers/opencode/commands/commit-msg.md
    git -C "$source" commit -qm 'update command fixture'
    dry="$(bash "$DEPLOY" migrate "$REPO" --dry-run)"
    assert_contains "$dry" 'Would make no provider link changes'
    [ "$(file_digest "$REPO/.opencode/commands/commit-msg.md")" != "$initial_digest" ] \
        || fail 'managed command link did not follow selected anchor revision'
    bash "$DEPLOY" migrate "$REPO" >/dev/null
    grep -q selected-anchor-revision "$REPO/.opencode/commands/commit-msg.md" \
        || fail 'managed command link lost selected anchor content'
    bash "$DEPLOY" status "$REPO" --provider opencode >/dev/null \
        || fail 'status is unhealthy after managed-command migration'
    pass 'migration preserves managed command links that follow selected anchor revisions'
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

test_command_link_modes_and_updates() {
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
    assert_eq "$(readlink "$REPO/.opencode/commands/commit-msg.md")" \
        "$update_source/providers/opencode/commands/commit-msg.md"
    printf '\nmanaged-v2\n' >> "$update_source/providers/opencode/commands/commit-msg.md"
    git -C "$update_source" add providers/opencode/commands/commit-msg.md
    git -C "$update_source" commit -qm v2
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    grep -q managed-v2 "$REPO/.opencode/commands/commit-msg.md" \
        || fail 'managed command link did not follow source update'

    new_repo portable-command
    bash "$DEPLOY" init "$REPO" --method submodule --url "$SOURCE_URL" >/dev/null
    bash "$DEPLOY" taken-export "$REPO" --provider opencode \
        --method submodule >/dev/null
    bash "$DEPLOY" command taken-export "$REPO" --provider opencode \
        --method submodule >/dev/null
    assert_eq "$(readlink "$REPO/.opencode/commands/taken-export.md")" \
        '../../.ai/ai.skillz/providers/opencode/commands/taken-export.md'
    git -C "$REPO" check-ignore -q -- .opencode/commands/taken-export.md \
        && fail 'portable command link was ignored'
    pass 'local command links follow source updates and portable links remain trackable'
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

    new_repo validate-runtime-msgs-file
    mkdir -p "$REPO/.claude/skills/commit-msg"
    printf malformed > "$REPO/.claude/skills/commit-msg/msgs"
    git -C "$REPO" add -f .claude/skills/commit-msg/msgs
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'runtime state is staged or tracked: .claude/skills/commit-msg/msgs'

    new_repo validate-taken-export-runtime
    mkdir -p "$REPO/.ai/taken/exports"
    printf tracked > "$REPO/.ai/taken/exports/item"
    git -C "$REPO" add -f .ai/taken/exports/item
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'runtime state is staged or tracked: .ai/taken/exports/item'

    new_repo validate-code-review-runtime
    mkdir -p "$REPO/.ai/code-review/reports"
    printf tracked > "$REPO/.ai/code-review/reports/result.json"
    git -C "$REPO" add -f .ai/code-review/reports/result.json
    assert_fails "$ROOT/scripts/validate-deployment.sh" "$REPO"
    assert_contains "$(<"$TMP_ROOT/failure.out")" \
        'runtime state is staged or tracked: .ai/code-review/reports/result.json'

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
    assert_contains "$output" 'Result: 34 deployed, 0 template skipped'
    [ -L "$REPO/.claude/skills/run-tests/SKILL.md" ] \
        || fail 'run-tests hybrid destination was not created'
    before="$(tree_digest "$REPO")"
    bash "$DEPLOY" all "$REPO" --provider all >/dev/null
    after="$(tree_digest "$REPO")"
    assert_eq "$after" "$before"
    assert_fails bash "$DEPLOY" '../py-codestyle' "$REPO"
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider vscode
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --method copy
    assert_fails bash "$DEPLOY" py-codestyle "$REPO" --provider
    pass 'all deploys hybrid skills, remains idempotent, and validates names/options strictly'
}

test_code_review_contract_assets() {
    python -m json.tool \
        "$ROOT/skills/code-review/references/review-result-v1.schema.json" \
        >/dev/null
    python "$ROOT/tests/test_gish_review_post.py"
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'explicitly authorizes test execution.'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        '-c core.fsmonitor=false'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'Test selection remains owned by `/run-tests`'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'trusted target-local deployment, including a safely resolved'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'supersedes reviewer-global auto-application'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'installed `py-codestyle` does not apply merely because'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'resolved `SKILL.md` remains physically within the target checkout'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'a submodule in the target repository'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'loaded by the harness from a user-approved source'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'user explicitly authorizes reading that exact resolved external path'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'Do not inspect an external `deploy-manifest.conf`'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'external configured root, directory link, or nested'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'Do not fetch, clone, or use a forge API solely for style discovery'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'Do not merge competing style'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        "target's instructions, formatter configuration, and nearby Python"
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        'Preserve quotations and evidence from'
    assert_file_contains \
        "$ROOT/skills/code-review/references/python-review.md" \
        "never changes the finding's severity"
    assert_file_contains \
        "$ROOT/skills/code-review/references/output-contract.md" \
        "target repository's deployed"
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'Reports in this runtime directory remain untracked'
    assert_file_contains \
        "$ROOT/skills/code-review/references/output-contract.md" \
        'JSON export remains local'
    assert_file_contains \
        "$ROOT/skills/code-review/references/output-contract.md" \
        'fingerprint: 23acc5fc36ab85c0'
    assert_file_contains \
        "$ROOT/skills/code-review/references/review-result-v1.schema.json" \
        '"delegated"'
    assert_file_contains \
        "$ROOT/skills/code-review/references/review-result-v1.schema.json" \
        '"open_questions"'
    assert_file_contains \
        "$ROOT/skills/code-review/references/review-result-v1.schema.json" \
        '"merge_base"'
    assert_file_contains \
        "$ROOT/skills/code-review/references/review-result-v1.schema.json" \
        '"symbol"'
    assert_file_contains "$ROOT/providers/opencode/commands/code-review.md" \
        'first-class `gish` transport'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'Delegate publication to `/gish review-post`'
    assert_file_contains "$ROOT/skills/code-review/SKILL.md" \
        'Never fall back silently.'
    assert_file_contains \
        "$ROOT/skills/code-review/references/output-contract.md" \
        'Bind approval to that digest'
    assert_file_contains "$ROOT/skills/gish/SKILL.md" \
        'review-post <backend> <num>'
    assert_file_contains \
        "$ROOT/skills/gish/references/review-publication.md" \
        '--raw-field event=COMMENT'
    assert_file_contains \
        "$ROOT/skills/gish/scripts/review-post.py" \
        'target PR head moved after review'
    assert_file_contains "$ROOT/README.md" '| `code-review` |'
    pass 'code-review schema and human-control contracts are present'
}

test_opencode_debug_if_available() {
    if ! command -v opencode >/dev/null 2>&1; then
        pass 'OpenCode debug validation skipped (opencode unavailable)'
        return 0
    fi
    new_repo opencode-debug
    bash "$DEPLOY" init "$REPO" --method symlink >/dev/null
    bash "$DEPLOY" code-review "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command code-review "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command commit-msg "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" run-tests "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command run-tests "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" taken-export "$REPO" --provider opencode >/dev/null
    bash "$DEPLOY" command taken-export "$REPO" --provider opencode >/dev/null
    local config_output="$TMP_ROOT/opencode-config.out"
    local skill_output="$TMP_ROOT/opencode-skill.out"
    (cd "$REPO" && OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
        OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
        opencode debug config > "$config_output")
    (cd "$REPO" && OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
        OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
        opencode debug skill > "$skill_output")
    assert_file_contains "$config_output" '"commit-msg"'
    assert_file_contains "$config_output" '"code-review"'
    assert_file_contains "$config_output" '"run-tests"'
    assert_file_contains "$config_output" '"taken-export"'
    assert_file_contains "$skill_output" '"name": "commit-msg"'
    assert_file_contains "$skill_output" '"name": "code-review"'
    assert_file_contains "$skill_output" '"name": "run-tests"'
    assert_file_contains "$skill_output" '"name": "taken-export"'
    assert_file_contains "$skill_output" \
        "\"location\": \"$REPO/.opencode/skills/commit-msg/SKILL.md\""
    pass 'OpenCode debug config and skill resolve deployed fixture'
}

prepare_source_repo
test_local_anchor_and_anchor_authority
test_subdirectory_resolves_repository_root
test_submodule_and_default_url
test_init_stage_preserves_gitmodules_index
test_submodule_init_boundaries
test_phase0_and_global_compatibility
test_global_skill_deployment_safety
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
test_run_tests_hybrid_migration_safety
test_local_tracking_and_portable_ignore_preflight
test_gitignore_integrity_and_inventory
test_direct_migration_dry_run
test_multi_asset_migration_ignore
test_direct_to_submodule_migration
test_migration_full_preflight_zero_mutation
test_tracked_command_copy_transition
test_migration_preserves_managed_command_link
test_legacy_submodule_relocation
test_json_skills_paths_inspection
test_init_option_consistency
test_command_link_modes_and_updates
test_update_behavior_and_broken_anchor
test_deployment_validator_failures
test_all_templates_invalid_args_and_idempotence
test_code_review_contract_assets
test_opencode_debug_if_available

printf '1..%d\n' "$PASS"
