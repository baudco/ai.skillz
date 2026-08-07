#!/usr/bin/env bash
# Provider-neutral ai.skillz deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
SKILLZ_ROOT="$(dirname "$SCRIPT_DIR")"
MANIFEST="$SKILLZ_ROOT/deploy-manifest.conf"
PATTERNS_CONF="$SKILLZ_ROOT/gitignore-patterns.conf"
ANCHOR_REL=".ai/ai.skillz"
DEFAULT_URL="https://github.com/baudco/ai.skillz.git"
IGNORE_CHANGED_IDS=()

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage:
  deploy.sh init <repo> [--method symlink|submodule] [--url URL] [--ref REF] [--stage]
  deploy.sh <skill> <repo> [--provider claude|opencode|all] [--method symlink|submodule] [--direct] [--stage] [--no-command]
  deploy.sh <skill> --global [--provider claude|all] [--method symlink] [--direct]
  deploy.sh all <repo> [--provider claude|opencode|all] [--method symlink|submodule] [--direct] [--stage] [--no-command]
  deploy.sh command <name|all> <repo> [--provider claude|opencode|all] [--method symlink|submodule] [--direct] [--stage]
  deploy.sh command <name|all> --global [--provider claude|all]
  deploy.sh update <repo> [--ref REF] [--stage]
  deploy.sh status <repo> [--provider claude|opencode|all]
  deploy.sh migrate <repo> [--dry-run] [--stage]
  deploy.sh gitignore <repo> [skill]

Defaults:
  Skill and command deployment defaults to provider "claude".
  Status defaults to provider "all". Init defaults to method "submodule".
  The default submodule URL is https://github.com/baudco/ai.skillz.git.

Methods:
  symlink   Create .ai/ai.skillz as an ignored link to this checkout.
  submodule Create .ai/ai.skillz as a portable git submodule.

Local symlink deployments use ignored absolute provider links. Submodule
deployments use trackable relative links through the provider-neutral anchor.
OpenCode skill deployment also installs manifest commands which depend on the
skill. Use --no-command for an explicit skill-only deployment.
--direct is retained as an explicit local-link compatibility alias.
Nothing is staged unless --stage is supplied; this script never commits.
EOF
}

need_value() {
    [ $# -ge 2 ] || die "$1 requires a value"
    [[ "$2" != --* ]] || die "$1 requires a value"
}

validate_name() {
    local name="$1" kind="$2"
    [[ "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] \
        || die "invalid $kind name: $name"
}

validate_provider() {
    case "$1" in
        claude|opencode|all) ;;
        *) die "invalid provider '$1' (expected claude, opencode, or all)" ;;
    esac
}

validate_method() {
    case "$1" in
        symlink|submodule) ;;
        *) die "invalid method '$1' (expected symlink or submodule)" ;;
    esac
}

validate_relative_path() {
    local path="$1"
    [[ "$path" != /* && "$path" != *'//'*
        && "$path" != '..' && "$path" != ../*
        && "$path" != */../* && "$path" != */.. ]] \
        || die "unsafe manifest path: $path"
}

canonical_repo() {
    local path="$1" physical top
    [[ "$path" != -* ]] || die "invalid target path: $path"
    [ -d "$path" ] || die "target repository does not exist: $path"
    physical="$(cd "$path" && pwd -P)"
    top="$(git -C "$physical" rev-parse --show-toplevel 2>/dev/null)" \
        || die "target is not a git worktree: $physical"
    TARGET="$(cd "$top" && pwd -P)"
}

get_manifest_skill_dependency() {
    local wanted="$1" kind name shape assets dependency rest
    MANIFEST_SKILL_DEPENDENCY=""
    while IFS='|' read -r kind name shape assets dependency rest; do
        [ "$kind" = skill ] || continue
        if [ "$name" = "$wanted" ]; then
            MANIFEST_SKILL_DEPENDENCY="$dependency"
            return 0
        fi
    done < "$MANIFEST"
    return 1
}

validate_skill_dependency_chain() {
    local start="$1" current="$1" dependency seen="|$1|"
    while get_manifest_skill_dependency "$current"; do
        dependency="$MANIFEST_SKILL_DEPENDENCY"
        [ -n "$dependency" ] && [ "$dependency" != - ] || return 0
        case "$seen" in
            *"|$dependency|"*)
                die "skill dependency cycle includes '$dependency'"
                ;;
        esac
        seen="$seen$dependency|"
        current="$dependency"
    done
    die "skill '$start' dependency record is missing: $current"
}

validate_manifest() {
    [ -f "$MANIFEST" ] || die "deployment manifest not found: $MANIFEST"
    local kind a b c d extra asset
    local seen_skills='|' seen_commands='|'
    local dependency trailing
    while IFS='|' read -r kind a b c d extra dependency trailing \
        || [ -n "$kind$a$b$c$d$extra$dependency$trailing" ]; do
        [ -z "$kind" ] && continue
        [[ "$kind" == \#* ]] && continue
        case "$kind" in
            skill)
                [ -z "${extra:-}${dependency:-}${trailing:-}" ] \
                     || die "invalid skill deployment manifest record"
                validate_name "$a" skill
                if [ -n "${d:-}" ] && [ "$d" != - ]; then
                    validate_name "$d" skill
                    [ "$d" != "$a" ] \
                        || die "skill '$a' cannot depend on itself"
                fi
                case "$b" in
                    generic|template) [ "$c" = "-" ] \
                        || die "skill '$a' must use '-' assets" ;;
                    hybrid)
                        [ -n "$c" ] && [ "$c" != "-" ] \
                            || die "hybrid skill '$a' has no assets"
                        IFS=',' read -ra MANIFEST_ASSETS <<< "$c"
                        for asset in "${MANIFEST_ASSETS[@]}"; do
                            validate_relative_path "$asset"
                        done
                        ;;
                    *) die "invalid shape '$b' for skill '$a'" ;;
                esac
                case "$seen_skills" in
                    *"|$a|"*) die "duplicate skill in deployment manifest: $a" ;;
                esac
                seen_skills="$seen_skills$a|"
                ;;
            command)
                [ -n "${extra:-}" ] && [ -z "${dependency:-}${trailing:-}" ] \
                    || die "invalid command deployment manifest record"
                case "$a" in claude|opencode) ;; *) die "invalid command provider: $a" ;; esac
                validate_name "$b" command
                validate_relative_path "$c"
                case "$d" in link|copy) ;; *) die "invalid command mode '$d'" ;; esac
                if [ "$extra" != - ]; then
                    validate_name "$extra" skill
                fi
                case "$seen_commands" in
                    *"|$a:$b|"*) die "duplicate command in deployment manifest: $a/$b" ;;
                esac
                seen_commands="$seen_commands$a:$b|"
                ;;
            *) die "invalid deployment manifest record type: $kind" ;;
        esac
    done < "$MANIFEST"
    while IFS='|' read -r kind a b c d extra; do
        [ "$kind" = skill ] || continue
        [ -n "${d:-}" ] && [ "$d" != - ] || continue
        case "$seen_skills" in
            *"|$d|"*) ;;
            *) die "skill '$a' dependency missing from manifest: $d" ;;
        esac
    done < "$MANIFEST"
    while IFS='|' read -r kind a b c d extra; do
        [ "$kind" = skill ] || continue
        validate_skill_dependency_chain "$a"
    done < "$MANIFEST"
    while IFS='|' read -r kind a b c d extra; do
        [ "$kind" = command ] || continue
        [ "$extra" != - ] || continue
        get_skill_record "$extra" \
            || die "command '$a/$b' dependency missing from manifest: $extra"
        [ "$SKILL_SHAPE" != template ] \
            || die "command '$a/$b' depends on template-only skill '$extra'"
    done < "$MANIFEST"
}

get_skill_record() {
    local wanted="$1" kind name shape assets dependency rest
    SKILL_SHAPE=""
    SKILL_ASSETS=""
    SKILL_DEPENDENCY=""
    while IFS='|' read -r kind name shape assets dependency rest; do
        [ "$kind" = skill ] || continue
        if [ "$name" = "$wanted" ]; then
            SKILL_SHAPE="$shape"
            SKILL_ASSETS="$assets"
            SKILL_DEPENDENCY="$dependency"
            return 0
        fi
    done < "$MANIFEST"
    return 1
}

get_command_record() {
    local wanted_provider="$1" wanted_name="$2"
    local kind provider name source mode dependency rest
    COMMAND_SOURCE=""
    COMMAND_MODE=""
    COMMAND_SKILL=""
    while IFS='|' read -r kind provider name source mode dependency rest; do
        [ "$kind" = command ] || continue
        if [ "$provider" = "$wanted_provider" ] && [ "$name" = "$wanted_name" ]; then
            COMMAND_SOURCE="$source"
            COMMAND_MODE="$mode"
            COMMAND_SKILL="$dependency"
            return 0
        fi
    done < "$MANIFEST"
    return 1
}

set_providers() {
    case "$1" in
        claude) PROVIDERS=(claude) ;;
        opencode) PROVIDERS=(opencode) ;;
        all) PROVIDERS=(claude opencode) ;;
    esac
}

provider_root() {
    case "$1" in
        claude) PROVIDER_ROOT=".claude" ;;
        opencode) PROVIDER_ROOT=".opencode" ;;
    esac
}

git_path_tracked() {
    git -C "$1" ls-files --error-unmatch -- "$2" >/dev/null 2>&1
}

tracking_description() {
    local target="$1" path="$2"
    if git_path_tracked "$target" "$path"; then
        TRACKING=tracked
    elif git -C "$target" check-ignore -q -- "$path"; then
        TRACKING=ignored
    else
        TRACKING=untracked
    fi
}

stage_paths() {
    local target="$1" stage="$2"
    shift 2
    [ "$stage" = yes ] || return 0
    [ $# -gt 0 ] || return 0
    local path value
    local stageable=()
    for path in "$@"; do
        [ "$path" != .gitignore ] || continue
        if [ -L "$target/$path" ]; then
            value="$(readlink "$target/$path")"
            if [[ "$value" = /* ]]; then
                printf '  Not staging local-only absolute link: %s\n' "$path"
                continue
            fi
        fi
        if { [ -e "$target/$path" ] || [ -L "$target/$path" ] \
            || git_path_tracked "$target" "$path"; } \
            && ! { ! git_path_tracked "$target" "$path" \
                && git -C "$target" check-ignore -q -- "$path"; }; then
            stageable+=("$path")
        fi
    done
    [ ${#stageable[@]} -eq 0 ] || git -C "$target" add -- "${stageable[@]}"
}

record_managed_path() {
    local candidate="$1" existing
    for existing in "${MANAGED_PATHS[@]}"; do
        [ "$existing" = "$candidate" ] && return 0
    done
    MANAGED_PATHS+=("$candidate")
}

record_ignore_change() {
    local candidate="$1" existing
    [ "${RECORD_IGNORE_CHANGES:-yes}" = yes ] || return 0
    for existing in "${IGNORE_CHANGED_IDS[@]}"; do
        [ "$existing" = "$candidate" ] && return 0
    done
    IGNORE_CHANGED_IDS+=("$candidate")
}

stage_ignore_changes() {
    local target="$1" stage="$2" id line inside begin end entry mode blob temp_dir
    local patterns=()
    [ "$stage" = yes ] || return 0
    [ ${#IGNORE_CHANGED_IDS[@]} -gt 0 ] || return 0
    if [ -L "$target/.gitignore" ]; then
        printf '  Not staging .gitignore because it is a symlink\n'
        return 0
    fi
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-ignore.XXXXXX")"
    entry="$(git -C "$target" ls-files -s -- .gitignore)"
    if [ -n "$entry" ]; then
        mode="${entry%% *}"
        git -C "$target" show :.gitignore > "$temp_dir/.gitignore"
    else
        mode=100644
        : > "$temp_dir/.gitignore"
    fi
    RECORD_IGNORE_CHANGES=no
    IGNORE_QUIET=yes
    for id in "${IGNORE_CHANGED_IDS[@]}"; do
        patterns=()
        inside=no
        begin="# BEGIN ai.skillz: $id"
        end="# END ai.skillz: $id"
        while IFS= read -r line || [ -n "$line" ]; do
            if [ "$line" = "$begin" ]; then
                inside=yes
                continue
            fi
            if [ "$line" = "$end" ]; then
                inside=no
                continue
            fi
            [ "$inside" = yes ] && patterns+=("$line")
        done < "$target/.gitignore"
        set_ignore_block "$temp_dir" "$id" "${patterns[@]}"
    done
    RECORD_IGNORE_CHANGES=yes
    IGNORE_QUIET=no
    blob="$(git -C "$target" hash-object -w "$temp_dir/.gitignore")"
    git -C "$target" update-index --add --cacheinfo "$mode,$blob,.gitignore"
    rm -f "$temp_dir/.gitignore"
    rmdir "$temp_dir"
}

validate_ignore_markers() {
    local file="$1" line active="" seen='|'
    [ -e "$file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^#\ BEGIN\ ai\.skillz:\ (.*)$ ]]; then
            [ -z "$active" ] || die "nested ai.skillz blocks in $file"
            active="${BASH_REMATCH[1]}"
            case "$seen" in
                *"|$active|"*) die "duplicate ai.skillz block '$active' in $file" ;;
            esac
            seen="$seen$active|"
        elif [[ "$line" =~ ^#\ END\ ai\.skillz:\ (.*)$ ]]; then
            [ -n "$active" ] || die "ai.skillz end marker precedes begin marker in $file"
            [ "$active" = "${BASH_REMATCH[1]}" ] \
                || die "mismatched ai.skillz markers in $file"
            active=""
        fi
    done < "$file"
    [ -z "$active" ] || die "unterminated ai.skillz block '$active' in $file"
}

preflight_gitignore() {
    local target="$1" resolved
    if [ -L "$target/.gitignore" ]; then
        resolve_existing_path "$target/.gitignore" \
            || die "refusing dangling .gitignore symlink: $target/.gitignore"
        resolved="$RESOLVED_PATH"
        case "$resolved" in
            "$target"/*) ;;
            *) die "refusing .gitignore symlink outside repository: $resolved" ;;
        esac
        die "refusing symlinked .gitignore because Git does not follow it: $target/.gitignore"
    fi
    validate_ignore_markers "$target/.gitignore"
}

preflight_gitmodules() {
    local target="$1"
    [ ! -L "$target/.gitmodules" ] \
        || die "refusing symlinked .gitmodules: $target/.gitmodules"
    [ ! -e "$target/.gitmodules" ] || [ -f "$target/.gitmodules" ] \
        || die ".gitmodules is not a regular file: $target/.gitmodules"
}

preflight_anchor_parent() {
    local target="$1"
    [ ! -L "$target/.ai" ] \
        || die "refusing symlinked anchor parent: $target/.ai"
    [ ! -e "$target/.ai" ] || [ -d "$target/.ai" ] \
        || die "anchor parent is not a directory: $target/.ai"
}

preflight_directory_chain() {
    local target="$1" relative="$2" current="$1" component resolved
    local old_ifs="$IFS"
    local components=()
    IFS='/' read -ra components <<< "$relative"
    IFS="$old_ifs"
    for component in "${components[@]}"; do
        [ -n "$component" ] || continue
        current="$current/$component"
        if [ -L "$current" ]; then
            resolve_existing_path "$current" \
                || die "refusing dangling provider parent symlink: $current"
            resolved="$RESOLVED_PATH"
            case "$resolved" in
                "$target"/*) ;;
                *) die "refusing provider parent symlink outside repository: $current -> $resolved" ;;
            esac
            die "refusing symlinked provider parent: $current -> $resolved"
        elif [ -e "$current" ] && [ ! -d "$current" ]; then
            die "provider destination parent is not a directory: $current"
        fi
    done
}

preflight_provider_base() {
    local target="$1" provider="$2"
    provider_root "$provider"
    preflight_directory_chain "$target" "$PROVIDER_ROOT"
    preflight_directory_chain "$target" "$PROVIDER_ROOT/skills"
    preflight_directory_chain "$target" "$PROVIDER_ROOT/commands"
}

preflight_global_skill_base() {
    local home="${HOME:-}" path
    GLOBAL_SKILLS_PARENT_CANONICAL=no
    [ -n "$home" ] && [[ "$home" = /* ]] \
        || die "--global requires an absolute HOME"
    [ -d "$home" ] || die "--global HOME does not exist: $home"
    path="$home/.claude"
    [ ! -L "$path" ] || die "refusing symlinked global skill parent: $path"
    [ ! -e "$path" ] || [ -d "$path" ] \
        || die "global skill parent is not a directory: $path"
    path="$home/.claude/skills"
    if [ -L "$path" ]; then
        if same_resolved_path "$path" "$SOURCE_ROOT/skills"; then
            GLOBAL_SKILLS_PARENT_CANONICAL=yes
            return 0
        fi
        die "refusing symlinked global skill parent: $path"
    fi
    [ ! -e "$path" ] || [ -d "$path" ] \
        || die "global skill parent is not a directory: $path"
}

source_copy_matches() {
    local source="$1" destination="$2"
    if [ -f "$source" ] && [ ! -L "$source" ] \
        && [ -f "$destination" ] && [ ! -L "$destination" ]; then
        cmp -s "$source" "$destination"
        return
    fi
    if [ -d "$source" ] && [ ! -L "$source" ] \
        && [ -d "$destination" ] && [ ! -L "$destination" ]; then
        diff -qr --no-dereference "$source" "$destination" >/dev/null
        return
    fi
    return 1
}

GLOBAL_SKILL_SWAP_ACTIVE=no

rollback_global_skill_swap() {
    [ "$GLOBAL_SKILL_SWAP_ACTIVE" = yes ] || return 0
    if [ ! -e "$GLOBAL_SKILL_SWAP_DESTINATION" ] \
        && [ ! -L "$GLOBAL_SKILL_SWAP_DESTINATION" ] \
        && [ -e "$GLOBAL_SKILL_SWAP_DIR/original" ]; then
        mv -T "$GLOBAL_SKILL_SWAP_DIR/original" \
            "$GLOBAL_SKILL_SWAP_DESTINATION" >/dev/null 2>&1 || true
    fi
}

arm_global_skill_swap() {
    GLOBAL_SKILL_SWAP_ACTIVE=yes
    GLOBAL_SKILL_SWAP_DESTINATION="$1"
    GLOBAL_SKILL_SWAP_DIR="$2"
    trap 'rollback_global_skill_swap' EXIT
    trap 'rollback_global_skill_swap; exit 129' HUP
    trap 'rollback_global_skill_swap; exit 130' INT
    trap 'rollback_global_skill_swap; exit 143' TERM
}

disarm_global_skill_swap() {
    trap - EXIT HUP INT TERM
    GLOBAL_SKILL_SWAP_ACTIVE=no
    GLOBAL_SKILL_SWAP_DESTINATION=""
    GLOBAL_SKILL_SWAP_DIR=""
}

replace_source_copy_with_link() {
    local source="$1" destination="$2" parent swap
    source_copy_matches "$source" "$destination" \
        || die "global source copy changed after preflight: $destination"
    parent="$(dirname "$destination")"
    swap="$(mktemp -d "$parent/.ai-skillz-link.XXXXXX")" \
        || die "failed to allocate global skill swap beside: $destination"
    if ! ln -s "$source" "$swap/link"; then
        rmdir "$swap" || true
        die "failed to prepare global skill link: $destination"
    fi
    arm_global_skill_swap "$destination" "$swap"
    if ! mv -T "$destination" "$swap/original"; then
        disarm_global_skill_swap
        rm -f "$swap/link"
        rmdir "$swap"
        die "failed to preserve global source copy before replacement: $destination"
    fi
    if ! source_copy_matches "$source" "$swap/original"; then
        mv -T "$swap/original" "$destination" \
            || die "global source copy changed and could not be restored: $destination"
        disarm_global_skill_swap
        rm -f "$swap/link"
        rmdir "$swap"
        die "global source copy changed during replacement: $destination"
    fi
    if mv -T "$swap/link" "$destination"; then
        rm -rf "$swap/original" \
            || die "installed global link but retained backup after cleanup failure: $swap/original"
        rmdir "$swap" \
            || die "installed global link but failed to remove swap directory: $swap"
        disarm_global_skill_swap
        return 0
    fi
    mv -T "$swap/original" "$destination" \
        || die "failed to restore global source copy after link failure: $destination"
    disarm_global_skill_swap
    rm -f "$swap/link"
    rmdir "$swap"
    die "failed to install global skill link: $destination"
}

# Replace one script-owned block without disturbing user-owned ignore lines.
set_ignore_block() {
    local target="$1" id="$2"
    shift 2
    local patterns=("$@")
    local gitignore="$target/.gitignore"
    local begin="# BEGIN ai.skillz: $id"
    local end="# END ai.skillz: $id"
    local temp found_begin=no line skipping=no

    preflight_gitignore "$target"

    temp="$(mktemp "$target/.gitignore.ai-skillz.XXXXXX")"
    if [ -e "$gitignore" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            if [ "$line" = "$begin" ]; then
                found_begin=yes
                skipping=yes
                if [ ${#patterns[@]} -gt 0 ]; then
                    printf '%s\n' "$begin" >> "$temp"
                    printf '%s\n' "${patterns[@]}" >> "$temp"
                    printf '%s\n' "$end" >> "$temp"
                fi
                continue
            fi
            if [ "$skipping" = yes ]; then
                if [ "$line" = "$end" ]; then
                    skipping=no
                fi
                continue
            fi
            printf '%s\n' "$line" >> "$temp"
        done < "$gitignore"
    fi

    if [ "$found_begin" = no ] && [ ${#patterns[@]} -gt 0 ]; then
        if [ -s "$temp" ] && [ -n "$(tail -n 1 "$temp")" ]; then
            printf '\n' >> "$temp"
        fi
        printf '%s\n' "$begin" >> "$temp"
        printf '%s\n' "${patterns[@]}" >> "$temp"
        printf '%s\n' "$end" >> "$temp"
    fi

    if [ -e "$gitignore" ] && cmp -s "$gitignore" "$temp"; then
        rm -f "$temp"
    elif [ ! -e "$gitignore" ] && [ ! -s "$temp" ]; then
        rm -f "$temp"
    else
        if [ -e "$gitignore" ]; then
            chmod --reference="$gitignore" "$temp"
        fi
        mv -f "$temp" "$gitignore"
        record_ignore_change "$id"
        [ "${IGNORE_QUIET:-no}" = yes ] \
            || printf '  Updated .gitignore block: %s\n' "$id"
    fi
}

ensure_anchor_ignore() {
    set_ignore_block "$1" anchor:symlink "/$ANCHOR_REL"
    require_effective_ignore "$1" "$ANCHOR_REL"
}

path_effectively_ignored() {
    local target="$1" relative="$2"
    if git -C "$target" check-ignore -q --no-index -- "$relative" \
        2>/dev/null; then
        return 0
    fi

    local temp_dir git_dir parent current="" component redirected=no
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-ignore-check.XXXXXX")"
    if [ -f "$target/.gitignore" ]; then
        cp "$target/.gitignore" "$temp_dir/.gitignore"
    else
        : > "$temp_dir/.gitignore"
    fi
    parent="$(dirname "$relative")"
    IFS='/' read -ra IGNORE_PARENT_COMPONENTS <<< "$parent"
    for component in "${IGNORE_PARENT_COMPONENTS[@]}"; do
        [ "$component" != . ] || continue
        current="${current:+$current/}$component"
        mkdir -p "$temp_dir/$current"
        if [ "$redirected" = no ] && [ -L "$target/$current" ]; then
            redirected=yes
        elif [ "$redirected" = no ] \
            && [ -f "$target/$current/.gitignore" ]; then
            cp "$target/$current/.gitignore" "$temp_dir/$current/.gitignore"
        fi
    done
    git_dir="$(git -C "$target" rev-parse --absolute-git-dir)"
    if git --git-dir="$git_dir" --work-tree="$temp_dir" \
        check-ignore -q --no-index -- "$relative"; then
        rm -rf "$temp_dir"
        return 0
    fi
    rm -rf "$temp_dir"
    return 1
}

require_effective_ignore() {
    local target="$1" relative="$2"
    path_effectively_ignored "$target" "$relative" \
        || die "managed local path is not effectively ignored: $relative"
}

ensure_runtime_ignores() {
    local skill="$1" target="$2"
    [ -f "$PATTERNS_CONF" ] || return 0
    local section="" line
    local patterns=()
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi
        [ "$section" = "$skill" ] || continue
        [ -n "$line" ] || continue
        patterns+=("$line")
    done < "$PATTERNS_CONF"
    if [ ${#patterns[@]} -gt 0 ]; then
        set_ignore_block "$target" "runtime:$skill" "${patterns[@]}"
        local pattern
        for pattern in "${patterns[@]}"; do
            require_effective_ignore "$target" "${pattern#/}"
        done
    fi
}

preflight_runtime_ignores() {
    local skill="$1" target="$2" section="" line pattern
    local patterns=()
    [ -f "$PATTERNS_CONF" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi
        [ "$section" = "$skill" ] && [ -n "$line" ] || continue
        patterns+=("$line")
    done < "$PATTERNS_CONF"
    for pattern in "${patterns[@]}"; do
        require_planned_ignore "$target" "runtime:$skill" \
            "${pattern#/}" "${patterns[@]}"
    done
}

direct_ignore_paths() {
    local provider="$1" skill="$2" shape="$3" assets="$4"
    provider_root "$provider"
    DIRECT_PATTERNS=()
    if [ "$shape" = generic ]; then
        DIRECT_PATTERNS+=("/$PROVIDER_ROOT/skills/$skill")
    elif [ "$shape" = hybrid ]; then
        local asset
        IFS=',' read -ra ASSET_LIST <<< "$assets"
        for asset in "${ASSET_LIST[@]}"; do
            DIRECT_PATTERNS+=("/$PROVIDER_ROOT/skills/$skill/$asset")
        done
    fi
}

inspect_anchor() {
    local target="$1" anchor="$1/$ANCHOR_REL" entry
    ANCHOR_MODE=missing
    ANCHOR_HEALTH=missing
    ANCHOR_SOURCE=""
    if [ -L "$anchor" ]; then
        ANCHOR_MODE=symlink
        if [ -e "$anchor" ] && [ -d "$anchor" ]; then
            ANCHOR_HEALTH=healthy
            ANCHOR_SOURCE="$(cd "$anchor" && pwd -P)"
        else
            ANCHOR_HEALTH=broken
        fi
    else
        entry="$(git -C "$target" ls-files -s -- "$ANCHOR_REL")"
        if get_submodule_registration "$target" "$ANCHOR_REL"; then
            ANCHOR_MODE=submodule
            if [ -f "$anchor/.git" ] \
                && git -C "$anchor" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
                ANCHOR_HEALTH=healthy
                ANCHOR_SOURCE="$anchor"
            elif [[ "$entry" = 160000\ * ]]; then
                ANCHOR_HEALTH=uninitialized
            else
                ANCHOR_MODE=invalid
                ANCHOR_HEALTH=invalid
                ANCHOR_SOURCE="$anchor"
            fi
        elif [ -e "$anchor" ]; then
            ANCHOR_MODE=invalid
            ANCHOR_HEALTH=invalid
            ANCHOR_SOURCE="$anchor"
        fi
    fi
}

legacy_anchor_registered() {
    local target="$1"
    [ -e "$target/.claude/ai.skillz" ] \
        || [ -L "$target/.claude/ai.skillz" ] \
        || { [ -f "$target/.gitmodules" ] \
            && git -C "$target" config -f .gitmodules \
                --get-regexp '^submodule\..*\.path$' 2>/dev/null \
                | grep -qE ' \.claude/ai\.skillz/?$'; }
}

require_anchor() {
    local target="$1" requested_method="$2"
    inspect_anchor "$target"
    [ "$ANCHOR_HEALTH" = healthy ] \
        || die "healthy $ANCHOR_REL anchor required (run: deploy.sh init '$target')"
    if [ -n "$requested_method" ] && [ "$ANCHOR_MODE" != "$requested_method" ]; then
        die "anchor method is $ANCHOR_MODE, not $requested_method"
    fi
    DEPLOY_METHOD="$ANCHOR_MODE"
    SOURCE_ROOT="$ANCHOR_SOURCE"
}

resolve_existing_path() {
    local path="$1" value parent base count=0
    [ -e "$path" ] || return 1
    while [ -L "$path" ]; do
        count=$((count + 1))
        [ "$count" -le 40 ] || return 1
        value="$(readlink "$path")"
        if [[ "$value" = /* ]]; then
            path="$value"
        else
            path="$(dirname "$path")/$value"
        fi
        parent="$(cd -P "$(dirname "$path")" 2>/dev/null && pwd)" || return 1
        base="$(basename "$path")"
        path="$parent/$base"
        [ -e "$path" ] || return 1
    done
    if [ -d "$path" ]; then
        RESOLVED_PATH="$(cd -P "$path" && pwd)"
    else
        parent="$(cd -P "$(dirname "$path")" && pwd)" || return 1
        RESOLVED_PATH="$parent/$(basename "$path")"
    fi
}

safe_link() {
    local target_value="$1" destination="$2" canonical_source="$3"
    local existing_resolved source_resolved
    [ -e "$canonical_source" ] \
        || die "canonical source is missing from deployment source: $canonical_source"
    if [ -L "$destination" ]; then
        if [ "$(readlink "$destination")" = "$target_value" ]; then
            return 0
        fi
        if resolve_existing_path "$destination"; then
            existing_resolved="$RESOLVED_PATH"
        else
            die "refusing to replace unrecognized broken symlink: $destination"
        fi
        resolve_existing_path "$canonical_source" \
            || die "cannot resolve canonical source: $canonical_source"
        source_resolved="$RESOLVED_PATH"
        [ "$existing_resolved" = "$source_resolved" ] \
            || die "refusing to replace unmanaged symlink: $destination"
        ln -sfn "$target_value" "$destination"
    elif [ -e "$destination" ]; then
        die "refusing to replace existing provider destination: $destination"
    else
        ln -s "$target_value" "$destination"
    fi
}

is_known_command_copy() {
    local file="$1" source_root="$2" source_rel="$3" file_blob commit source_blob
    cmp -s "$file" "$source_root/$source_rel" && return 0
    git -C "$source_root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
    file_blob="$(git hash-object "$file")" || return 1
    for commit in $(git -C "$source_root" log --format=%H --all -- "$source_rel" 2>/dev/null); do
        source_blob="$(git -C "$source_root" rev-parse "$commit:$source_rel" 2>/dev/null || true)"
        [ -n "$source_blob" ] && [ "$file_blob" = "$source_blob" ] && return 0
    done
    return 1
}

atomic_copy() {
    local source="$1" destination="$2" source_root="$3" source_rel="$4" temp
    if [ -f "$destination" ] && [ ! -L "$destination" ] \
        && cmp -s "$source" "$destination"; then
        return 0
    fi
    if [ -L "$destination" ]; then
        local existing_resolved source_resolved
        resolve_existing_path "$destination" \
            || die "refusing to replace unrecognized broken command symlink: $destination"
        existing_resolved="$RESOLVED_PATH"
        resolve_existing_path "$source" || die "cannot resolve command source: $source"
        source_resolved="$RESOLVED_PATH"
        [ "$existing_resolved" = "$source_resolved" ] \
            || die "refusing to replace unmanaged command symlink: $destination"
    elif [ -e "$destination" ]; then
        [ -f "$destination" ] \
            || die "command destination is not a regular file: $destination"
        is_known_command_copy "$destination" "$source_root" "$source_rel" \
            || die "refusing to overwrite user-authored command file: $destination"
    fi
    temp="$(mktemp "$(dirname "$destination")/.ai-skillz-command.XXXXXX")"
    cp "$source" "$temp"
    mv -f "$temp" "$destination"
}

relative_skill_target() {
    local shape="$1" skill="$2" asset="${3:-}"
    if [ "$shape" = generic ]; then
        LINK_TARGET="../../$ANCHOR_REL/skills/$skill"
    else
        LINK_TARGET="../../../$ANCHOR_REL/skills/$skill/$asset"
    fi
}

select_deployment_source() {
    local target="$1" method="$2" explicit_direct="$3"
    inspect_anchor "$target"
    DEPLOY_DIRECT="$explicit_direct"
    if [ "$explicit_direct" = yes ]; then
        [ -z "$method" ] || [ "$method" = symlink ] \
            || die "--direct requires --method symlink"
        DEPLOY_DIRECT=yes
        DEPLOY_METHOD=symlink
        SOURCE_ROOT="$SKILLZ_ROOT"
    elif [ "$method" = symlink ]; then
        if [ "$ANCHOR_HEALTH" = healthy ]; then
            [ "$ANCHOR_MODE" = symlink ] \
                || die "anchor method is $ANCHOR_MODE, not symlink"
        else
            [ "$ANCHOR_HEALTH" = missing ] \
                || die "refusing deployment with $ANCHOR_HEALTH anchor"
        fi
        DEPLOY_DIRECT=yes
        DEPLOY_METHOD=symlink
        if [ "$ANCHOR_MODE" = symlink ] && [ "$ANCHOR_HEALTH" = healthy ]; then
            SOURCE_ROOT="$ANCHOR_SOURCE"
        else
            SOURCE_ROOT="$SKILLZ_ROOT"
        fi
    elif [ "$method" = submodule ]; then
        require_anchor "$target" submodule
        DEPLOY_DIRECT=no
    elif [ "$ANCHOR_HEALTH" = healthy ]; then
        if [ "$ANCHOR_MODE" = symlink ]; then
            DEPLOY_DIRECT=yes
            DEPLOY_METHOD=symlink
            SOURCE_ROOT="$ANCHOR_SOURCE"
        else
            require_anchor "$target" submodule
            DEPLOY_DIRECT=no
        fi
    elif [ "$ANCHOR_HEALTH" = missing ] \
        && { [ -z "$method" ] || [ "$method" = symlink ]; }; then
        DEPLOY_DIRECT=yes
        DEPLOY_METHOD=symlink
        SOURCE_ROOT="$SKILLZ_ROOT"
    else
        [ "$ANCHOR_HEALTH" = missing ] \
            || die "refusing deployment with $ANCHOR_HEALTH anchor"
        die "healthy $ANCHOR_REL submodule required (run init first)"
    fi
}

require_local_path_untracked() {
    local target="$1" relative="$2"
    [ "$target" = "$SOURCE_ROOT" ] && return 0
    git_path_tracked "$target" "$relative" \
        && die "local provider destination is tracked; untrack it before deployment: $relative"
    return 0
}

require_portable_path_trackable() {
    local target="$1" relative="$2"
    git_path_tracked "$target" "$relative" && return 0
    if git -C "$target" check-ignore -q --no-index -- "$relative"; then
        die "portable provider destination is ignored; narrow the ignore rule before deployment: $relative"
    fi
}

require_migration_path_trackable() {
    local target="$1" relative="$2" ignore_id="$3"
    git_path_tracked "$target" "$relative" && return 0
    local temp_dir git_dir line skipping=no ignored=no parent current="" component
    local begin="# BEGIN ai.skillz: $ignore_id"
    local end="# END ai.skillz: $ignore_id"
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-ignore-check.XXXXXX")"
    : > "$temp_dir/.gitignore"
    if [ -f "$target/.gitignore" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            if [ "$line" = "$begin" ]; then
                skipping=yes
                continue
            fi
            if [ "$skipping" = yes ]; then
                [ "$line" != "$end" ] || skipping=no
                continue
            fi
            printf '%s\n' "$line" >> "$temp_dir/.gitignore"
        done < "$target/.gitignore"
    fi
    parent="$(dirname "$relative")"
    IFS='/' read -ra IGNORE_PARENT_COMPONENTS <<< "$parent"
    for component in "${IGNORE_PARENT_COMPONENTS[@]}"; do
        [ "$component" != . ] || continue
        current="${current:+$current/}$component"
        mkdir -p "$temp_dir/$current"
        if [ -f "$target/$current/.gitignore" ]; then
            cp "$target/$current/.gitignore" "$temp_dir/$current/.gitignore"
        fi
    done
    git_dir="$(git -C "$target" rev-parse --absolute-git-dir)"
    git --git-dir="$git_dir" --work-tree="$temp_dir" \
        check-ignore -q --no-index -- "$relative" && ignored=yes
    rm -rf "$temp_dir"
    [ "$ignored" = no ] \
        || die "portable provider destination is ignored outside its managed block; narrow the ignore rule before migration: $relative"
}

require_planned_ignore() {
    local target="$1" id="$2" relative="$3"
    shift 3
    local patterns=("$@")
    local temp_dir git_dir parent current="" component
    local old_record="${RECORD_IGNORE_CHANGES:-yes}"
    local old_quiet="${IGNORE_QUIET:-no}"
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-ignore-check.XXXXXX")"
    if [ -f "$target/.gitignore" ]; then
        cp "$target/.gitignore" "$temp_dir/.gitignore"
    else
        : > "$temp_dir/.gitignore"
    fi
    parent="$(dirname "$relative")"
    IFS='/' read -ra IGNORE_PARENT_COMPONENTS <<< "$parent"
    for component in "${IGNORE_PARENT_COMPONENTS[@]}"; do
        [ "$component" != . ] || continue
        current="${current:+$current/}$component"
        mkdir -p "$temp_dir/$current"
        if [ -f "$target/$current/.gitignore" ]; then
            cp "$target/$current/.gitignore" "$temp_dir/$current/.gitignore"
        fi
    done
    RECORD_IGNORE_CHANGES=no
    IGNORE_QUIET=yes
    set_ignore_block "$temp_dir" "$id" "${patterns[@]}"
    RECORD_IGNORE_CHANGES="$old_record"
    IGNORE_QUIET="$old_quiet"
    git_dir="$(git -C "$target" rev-parse --absolute-git-dir)"
    if ! git --git-dir="$git_dir" --work-tree="$temp_dir" \
        check-ignore -q --no-index -- "$relative"; then
        rm -rf "$temp_dir"
        die "managed local path would not be effectively ignored: $relative"
    fi
    rm -rf "$temp_dir"
}

recognized_legacy_run_tests_link() {
    recognized_source_root "$1" run-tests "" \
        && [ -f "$RECOGNIZED_ROOT/deploy-manifest.conf" ] \
        && grep -q '^skill|run-tests|hybrid|SKILL.md$' \
            "$RECOGNIZED_ROOT/deploy-manifest.conf"
}

preflight_skill_provider() {
    local skill="$1" target="$2" provider="$3"
    local source_root asset destination asset_destination
    provider_root "$provider"
    preflight_directory_chain "$target" "$PROVIDER_ROOT/skills"
    source_root="$SOURCE_ROOT/skills/$skill"
    destination="$target/$PROVIDER_ROOT/skills/$skill"
    preflight_runtime_ignores "$skill" "$target"
    if [ "$DEPLOY_DIRECT" = yes ]; then
        direct_ignore_paths "$provider" "$skill" "$SKILL_SHAPE" "$SKILL_ASSETS"
        local pattern
        for pattern in "${DIRECT_PATTERNS[@]}"; do
            require_planned_ignore "$target" "direct:symlink:$provider:$skill" \
                "${pattern#/}" "${DIRECT_PATTERNS[@]}"
        done
    fi
    [ "$SKILL_SHAPE" != template ] || return 0
    [ -d "$source_root" ] || die "manifest skill source missing: $source_root"
    if [ "$SKILL_SHAPE" = generic ]; then
        if [ "$DEPLOY_DIRECT" = yes ]; then
            require_local_path_untracked "$target" "$PROVIDER_ROOT/skills/$skill"
        else
            require_portable_path_trackable "$target" "$PROVIDER_ROOT/skills/$skill"
        fi
        [ -f "$source_root/SKILL.md" ] \
            || die "generic skill has no SKILL.md in deployment source: $skill"
        if [ -e "$destination" ] || [ -L "$destination" ]; then
            [ -L "$destination" ] && same_resolved_path "$destination" "$source_root" \
                || die "refusing unmanaged provider destination: $destination"
        fi
        return 0
    fi
    if [ -L "$destination" ]; then
        [ "$skill" = run-tests ] && recognized_legacy_run_tests_link "$destination" \
            || die "refusing hybrid provider directory symlink: $destination"
        if [ "$DEPLOY_DIRECT" = yes ]; then
            require_local_path_untracked "$target" "$PROVIDER_ROOT/skills/$skill"
        else
            require_portable_path_trackable "$target" \
                "$PROVIDER_ROOT/skills/$skill/SKILL.md"
        fi
        return 0
    fi
    [ ! -e "$destination" ] || [ -d "$destination" ] \
        || die "hybrid provider destination is not a directory: $destination"
    if [ "$skill" = run-tests ] && [ -d "$destination" ]; then
        if [ -e "$destination/SKILL.md" ] && [ ! -L "$destination/SKILL.md" ]; then
            die "local run-tests/SKILL.md exists; extract project-specific guidance into test-harness-reference.md before deploying"
        fi
        if [ -e "$destination/test-harness-reference.md" ] \
            || [ -L "$destination/test-harness-reference.md" ]; then
            [ -f "$destination/test-harness-reference.md" ] \
                && [ ! -L "$destination/test-harness-reference.md" ] \
                || die "test-harness-reference.md must be a regular local file"
        fi
    fi
    preflight_directory_chain "$target" "$PROVIDER_ROOT/skills/$skill"
    IFS=',' read -ra ASSET_LIST <<< "$SKILL_ASSETS"
    for asset in "${ASSET_LIST[@]}"; do
        if [ "$DEPLOY_DIRECT" = yes ]; then
            require_local_path_untracked "$target" \
                "$PROVIDER_ROOT/skills/$skill/$asset"
        else
            require_portable_path_trackable "$target" \
                "$PROVIDER_ROOT/skills/$skill/$asset"
        fi
        [ -e "$source_root/$asset" ] \
            || die "hybrid skill asset missing from deployment source: $source_root/$asset"
        asset_destination="$destination/$asset"
        preflight_directory_chain "$target" \
            "$(dirname "$PROVIDER_ROOT/skills/$skill/$asset")"
        if [ -e "$asset_destination" ] || [ -L "$asset_destination" ]; then
            [ -L "$asset_destination" ] \
                && same_resolved_path "$asset_destination" "$source_root/$asset" \
                || die "refusing unmanaged hybrid asset: $asset_destination"
        fi
    done
}

deploy_skill_provider() {
    local skill="$1" target="$2" provider="$3" direct="$4"
    provider_root "$provider"
    local destination="$target/$PROVIDER_ROOT/skills/$skill"
    local source_root="$SOURCE_ROOT/skills/$skill"
    local asset asset_destination

    if [ "$SKILL_SHAPE" = template ]; then
        printf 'SKIP %s for %s (template-only)\n' "$skill" "$provider"
        return 2
    fi

    [ -d "$source_root" ] || die "manifest skill source missing: $source_root"
    mkdir -p "$(dirname "$destination")"
    if [ "$SKILL_SHAPE" = generic ]; then
        [ -f "$source_root/SKILL.md" ] \
            || die "generic skill has no SKILL.md: $skill"
        if [ "$direct" = yes ]; then
            safe_link "$source_root" "$destination" "$source_root"
        else
            relative_skill_target generic "$skill"
            safe_link "$LINK_TARGET" "$destination" "$source_root"
        fi
        record_managed_path "$PROVIDER_ROOT/skills/$skill"
    else
        if [ -L "$destination" ]; then
            [ "$skill" = run-tests ] \
                || die "refusing to replace hybrid provider directory symlink: $destination"
            rm "$destination"
            printf '  Replaced legacy run-tests directory symlink\n'
        fi
        [ ! -e "$destination" ] || [ -d "$destination" ] \
            || die "hybrid provider destination is not a directory: $destination"
        mkdir -p "$destination"
        IFS=',' read -ra ASSET_LIST <<< "$SKILL_ASSETS"
        for asset in "${ASSET_LIST[@]}"; do
            [ -e "$source_root/$asset" ] \
                || die "hybrid skill asset missing: $source_root/$asset"
            asset_destination="$destination/$asset"
            mkdir -p "$(dirname "$asset_destination")"
            if [ "$direct" = yes ]; then
                safe_link "$source_root/$asset" "$asset_destination" "$source_root/$asset"
            else
                relative_skill_target hybrid "$skill" "$asset"
                safe_link "$LINK_TARGET" "$asset_destination" "$source_root/$asset"
            fi
            record_managed_path "$PROVIDER_ROOT/skills/$skill/$asset"
        done
    fi

    ensure_runtime_ignores "$skill" "$target"
    if [ "$direct" = yes ]; then
        direct_ignore_paths "$provider" "$skill" "$SKILL_SHAPE" "$SKILL_ASSETS"
        set_ignore_block "$target" "direct:symlink:$provider:$skill" \
            "${DIRECT_PATTERNS[@]}"
        local pattern
        for pattern in "${DIRECT_PATTERNS[@]}"; do
            require_effective_ignore "$target" "${pattern#/}"
        done
    else
        set_ignore_block "$target" "direct:symlink:$provider:$skill"
    fi
    printf 'Deployed %s to %s/skills/%s (%s)\n' \
        "$skill" "$PROVIDER_ROOT" "$skill" \
        "$([ "$direct" = yes ] && printf 'local-only absolute' || printf 'relative via anchor')"
}

preflight_global_skill() {
    local skill="$1" source="$SOURCE_ROOT/skills/$skill"
    local destination="$HOME/.claude/skills/$skill" asset asset_destination
    [ "$SKILL_SHAPE" != template ] || return 0
    [ -d "$source" ] || die "manifest skill source missing: $source"
    [ -f "$source/SKILL.md" ] || die "global skill has no SKILL.md: $skill"
    if [ "$SKILL_SHAPE" = generic ]; then
        if [ -e "$destination" ] || [ -L "$destination" ]; then
            if [ -L "$destination" ]; then
                same_resolved_path "$destination" "$source" \
                    || die "refusing unmanaged global skill destination: $destination"
            else
                source_copy_matches "$source" "$destination" \
                    || die "refusing unmanaged global skill destination: $destination"
            fi
        fi
        return 0
    fi
    if [ -L "$destination" ]; then
        die "refusing global hybrid skill directory symlink: $destination"
    fi
    [ ! -e "$destination" ] || [ -d "$destination" ] \
        || die "global hybrid skill destination is not a directory: $destination"
    IFS=',' read -ra ASSET_LIST <<< "$SKILL_ASSETS"
    for asset in "${ASSET_LIST[@]}"; do
        [ -e "$source/$asset" ] \
            || die "global hybrid skill asset missing: $source/$asset"
        preflight_directory_chain "$destination" "$(dirname "$asset")"
        asset_destination="$destination/$asset"
        if [ -e "$asset_destination" ] || [ -L "$asset_destination" ]; then
            if [ -L "$asset_destination" ]; then
                same_resolved_path "$asset_destination" "$source/$asset" \
                    || die "refusing unmanaged global hybrid asset: $asset_destination"
            else
                source_copy_matches "$source/$asset" "$asset_destination" \
                    || die "refusing unmanaged global hybrid asset: $asset_destination"
            fi
        fi
    done
}

global_skill_deployment_healthy() {
    local skill="$1" source destination
    local shape assets asset asset_destination
    source="$SOURCE_ROOT/skills/$skill"
    destination="$HOME/.claude/skills/$skill"
    get_skill_record "$skill" || return 1
    shape="$SKILL_SHAPE"
    assets="$SKILL_ASSETS"
    [ "$shape" != template ] || return 1
    if [ "$GLOBAL_SKILLS_PARENT_CANONICAL" = yes ]; then
        [ -f "$source/SKILL.md" ]
        return
    fi
    if [ "$shape" = generic ]; then
        if [ -L "$destination" ]; then
            same_resolved_path "$destination" "$source"
        else
            [ -d "$destination" ] \
                && source_copy_matches "$source" "$destination"
        fi
        return
    fi
    [ -d "$destination" ] && [ ! -L "$destination" ] || return 1
    IFS=',' read -ra ASSET_LIST <<< "$assets"
    for asset in "${ASSET_LIST[@]}"; do
        asset_destination="$destination/$asset"
        if [ -L "$asset_destination" ]; then
            same_resolved_path "$asset_destination" "$source/$asset" \
                || return 1
        else
            [ -e "$asset_destination" ] \
                && source_copy_matches "$source/$asset" "$asset_destination" \
                || return 1
        fi
    done
}

deploy_global_skill() {
    local skill="$1" source="$SOURCE_ROOT/skills/$skill"
    local destination="$HOME/.claude/skills/$skill" asset asset_destination
    mkdir -p "$HOME/.claude/skills"
    if [ "$SKILL_SHAPE" = generic ]; then
        if [ -e "$destination" ] && [ ! -L "$destination" ]; then
            replace_source_copy_with_link "$source" "$destination"
        else
            safe_link "$source" "$destination" "$source"
        fi
    else
        mkdir -p "$destination"
        IFS=',' read -ra ASSET_LIST <<< "$SKILL_ASSETS"
        for asset in "${ASSET_LIST[@]}"; do
            asset_destination="$destination/$asset"
            mkdir -p "$(dirname "$asset_destination")"
            if [ -e "$asset_destination" ] && [ ! -L "$asset_destination" ]; then
                replace_source_copy_with_link "$source/$asset" "$asset_destination"
            else
                safe_link "$source/$asset" "$asset_destination" "$source/$asset"
            fi
        done
    fi
    printf 'Deployed %s to ~/.claude/skills/%s (global absolute)\n' \
        "$skill" "$skill"
}

deploy_skill() {
    local skill="$1"
    shift
    local target_arg="" provider=claude method="" direct=no stage=no global=no
    local auto_commands=yes
    while [ $# -gt 0 ]; do
        case "$1" in
            --provider) need_value "$@"; provider="$2"; shift 2 ;;
            --method) need_value "$@"; method="$2"; shift 2 ;;
            --direct) direct=yes; shift ;;
            --stage) stage=yes; shift ;;
            --no-command) auto_commands=no; shift ;;
            --global) global=yes; shift ;;
            --*) die "unknown option: $1" ;;
            *)
                [ -z "$target_arg" ] || die "unexpected argument: $1"
                target_arg="$1"
                shift
                ;;
        esac
    done
    validate_name "$skill" skill
    validate_provider "$provider"
    [ -z "$method" ] || validate_method "$method"
    get_skill_record "$skill" || die "skill '$skill' is not in the deployment manifest"
    local skill_dependency="$SKILL_DEPENDENCY"
    if [ "$global" = yes ]; then
        [ -z "$target_arg" ] || die "--global does not accept a target repository"
        [ "$stage" = no ] || die "--stage is invalid with --global"
        [ "$auto_commands" = yes ] \
            || die "--no-command is invalid with --global"
        [ -z "$method" ] || [ "$method" = symlink ] \
            || die "--global supports only --method symlink"
        [ "$provider" != opencode ] \
            || die "--global is supported only for Claude skills"
        SOURCE_ROOT="$SKILLZ_ROOT"
        preflight_global_skill_base
        if [ -n "$skill_dependency" ] && [ "$skill_dependency" != - ]; then
            global_skill_deployment_healthy "$skill_dependency" \
                || die "skill '$skill' requires healthy global skill '$skill_dependency'"
            get_skill_record "$skill"
        fi
        preflight_global_skill "$skill"
        if [ "$GLOBAL_SKILLS_PARENT_CANONICAL" = yes ]; then
            if [ "$SKILL_SHAPE" = template ]; then
                printf 'SKIP %s for global Claude (template-only)\n' "$skill"
                printf 'Result: 0 deployed, 1 template skipped\n'
            else
                printf 'Global Claude skills already use canonical parent: %s\n' \
                    "$HOME/.claude/skills"
                printf 'Result: 1 deployed, 0 template skipped\n'
            fi
            return 0
        fi
        if [ "$SKILL_SHAPE" = template ]; then
            printf 'SKIP %s for global Claude (template-only)\n' "$skill"
            printf 'Result: 0 deployed, 1 template skipped\n'
            return 0
        fi
        deploy_global_skill "$skill"
        printf 'Result: 1 deployed, 0 template skipped\n'
        return 0
    fi
    [ -n "$target_arg" ] || die "missing <target-repo>"
    canonical_repo "$target_arg"
    preflight_gitignore "$TARGET"
    set_providers "$provider"

    select_deployment_source "$TARGET" "$method" "$direct"
    direct="$DEPLOY_DIRECT"

    local deployed=0 skipped=0 selected_provider
    local command_count=0 job
    MANAGED_PATHS=()
    if [ -n "$skill_dependency" ] && [ "$skill_dependency" != - ]; then
        for selected_provider in "${PROVIDERS[@]}"; do
            skill_deployment_healthy \
                "$TARGET" "$selected_provider" "$skill_dependency" \
                || die "skill '$skill' requires healthy $selected_provider skill '$skill_dependency'"
        done
        get_skill_record "$skill"
    fi
    for selected_provider in "${PROVIDERS[@]}"; do
        preflight_skill_provider "$skill" "$TARGET" "$selected_provider"
    done
    COMMAND_JOBS=()
    if [ "$auto_commands" = yes ] && providers_include_opencode; then
        collect_skill_command_jobs "$skill"
        for job in "${COMMAND_JOBS[@]}"; do
            preflight_command_job "$job" "$direct" no "$skill"
        done
    fi
    for selected_provider in "${PROVIDERS[@]}"; do
        if deploy_skill_provider "$skill" "$TARGET" "$selected_provider" "$direct"; then
            deployed=$((deployed + 1))
        else
            [ $? -eq 2 ] || return 1
            skipped=$((skipped + 1))
        fi
    done
    deploy_command_jobs "$TARGET" "$direct" no
    command_count="$COMMAND_DEPLOYED"

    stage_paths "$TARGET" "$stage" "${MANAGED_PATHS[@]}"
    stage_ignore_changes "$TARGET" "$stage"
    printf 'Result: %d deployed, %d template skipped, %d command deployment(s)\n' \
        "$deployed" "$skipped" "$command_count"
}

deploy_all() {
    local target_arg="" provider=claude method="" direct=no stage=no
    local auto_commands=yes
    while [ $# -gt 0 ]; do
        case "$1" in
            --provider) need_value "$@"; provider="$2"; shift 2 ;;
            --method) need_value "$@"; method="$2"; shift 2 ;;
            --direct) direct=yes; shift ;;
            --stage) stage=yes; shift ;;
            --no-command) auto_commands=no; shift ;;
            --*) die "unknown option: $1" ;;
            *) [ -z "$target_arg" ] || die "unexpected argument: $1"; target_arg="$1"; shift ;;
        esac
    done
    validate_provider "$provider"
    [ -z "$method" ] || validate_method "$method"
    [ -n "$target_arg" ] || die "missing <target-repo>"
    canonical_repo "$target_arg"
    preflight_gitignore "$TARGET"
    select_deployment_source "$TARGET" "$method" "$direct"
    direct="$DEPLOY_DIRECT"

    local kind skill shape assets dependency rest deployed=0 skipped=0
    local selected_provider command_count=0 job
    set_providers "$provider"
    MANAGED_PATHS=()
    while IFS='|' read -r kind skill shape assets dependency rest; do
        [ "$kind" = skill ] || continue
        SKILL_SHAPE="$shape"
        SKILL_ASSETS="$assets"
        for selected_provider in "${PROVIDERS[@]}"; do
            preflight_skill_provider "$skill" "$TARGET" "$selected_provider"
        done
    done < "$MANIFEST"
    COMMAND_JOBS=()
    if [ "$auto_commands" = yes ] && providers_include_opencode; then
        while IFS='|' read -r kind skill shape assets dependency rest; do
            [ "$kind" = skill ] || continue
            collect_skill_command_jobs "$skill"
        done < "$MANIFEST"
        for job in "${COMMAND_JOBS[@]}"; do
            preflight_command_job "$job" "$direct" no '*'
        done
    fi
    while IFS='|' read -r kind skill shape assets dependency rest; do
        [ "$kind" = skill ] || continue
        SKILL_SHAPE="$shape"
        SKILL_ASSETS="$assets"
        for selected_provider in "${PROVIDERS[@]}"; do
            if [ -n "$dependency" ] && [ "$dependency" != - ]; then
                skill_deployment_healthy \
                    "$TARGET" "$selected_provider" "$dependency" \
                    || die "skill '$skill' requires healthy $selected_provider skill '$dependency'"
                SKILL_SHAPE="$shape"
                SKILL_ASSETS="$assets"
            fi
            if deploy_skill_provider "$skill" "$TARGET" "$selected_provider" "$direct"; then
                deployed=$((deployed + 1))
            else
                [ $? -eq 2 ] || return 1
                skipped=$((skipped + 1))
            fi
        done
    done < "$MANIFEST"
    deploy_command_jobs "$TARGET" "$direct" no
    command_count="$COMMAND_DEPLOYED"
    stage_paths "$TARGET" "$stage" "${MANAGED_PATHS[@]}"
    stage_ignore_changes "$TARGET" "$stage"
    printf 'Result: %d deployed, %d template skipped, %d command deployment(s)\n' \
        "$deployed" "$skipped" "$command_count"
}

add_submodule_without_staging() {
    local target="$1" url="$2" index temp_index
    index="$(git -C "$target" rev-parse --git-path index)"
    case "$index" in /*) ;; *) index="$target/$index" ;; esac
    temp_index="$(mktemp "${TMPDIR:-/tmp}/ai-skillz-index.XXXXXX")"
    if [ -f "$index" ]; then
        cp "$index" "$temp_index"
    else
        rm -f "$temp_index"
    fi
    if ! GIT_INDEX_FILE="$temp_index" \
        git -c protocol.file.allow=always -C "$target" \
            submodule add "$url" "$ANCHOR_REL"; then
        rm -f "$temp_index"
        return 1
    fi
    rm -f "$temp_index"
}

rollback_new_submodule() {
    local target="$1" backup="$2" had_gitmodules="$3" name="" modules_path
    if get_submodule_registration "$target" "$ANCHOR_REL"; then
        name="$SUBMODULE_NAME"
        git -C "$target" submodule deinit -f -- "$ANCHOR_REL" >/dev/null 2>&1 \
            || true
    fi
    rm -rf "$target/$ANCHOR_REL"
    rmdir "$target/.ai" >/dev/null 2>&1 || true
    if [ -n "$name" ]; then
        modules_path="$(git -C "$target" rev-parse --git-path "modules/$name")"
        case "$modules_path" in /*) ;; *) modules_path="$target/$modules_path" ;; esac
        rm -rf "$modules_path"
        git -C "$target" config --remove-section "submodule.$name" \
            >/dev/null 2>&1 || true
    fi
    if [ "$had_gitmodules" = yes ]; then
        cp "$backup" "$target/.gitmodules"
    else
        rm -f "$target/.gitmodules"
    fi
}

rollback_initialized_submodule() {
    local target="$1" modules_path="$2" modules_existed="$3"
    git -C "$target" submodule deinit -f -- "$ANCHOR_REL" >/dev/null 2>&1 \
        || true
    if [ "$modules_existed" = no ] && [ -n "$modules_path" ]; then
        rm -rf "$modules_path"
    fi
}

stage_submodule_registration() {
    local target="$1" path="$2" entry mode temp_dir blob
    get_submodule_registration "$target" "$path" \
        || die "submodule registration missing for staging: $path"
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-gitmodules.XXXXXX")"
    entry="$(git -C "$target" ls-files -s -- .gitmodules)"
    if [ -n "$entry" ]; then
        mode="${entry%% *}"
        git -C "$target" show :.gitmodules > "$temp_dir/.gitmodules"
    else
        mode=100644
        : > "$temp_dir/.gitmodules"
    fi
    git config -f "$temp_dir/.gitmodules" --replace-all \
        "submodule.$SUBMODULE_NAME.path" "$path"
    git config -f "$temp_dir/.gitmodules" --replace-all \
        "submodule.$SUBMODULE_NAME.url" "$SUBMODULE_URL"
    blob="$(git -C "$target" hash-object -w "$temp_dir/.gitmodules")"
    git -C "$target" update-index --add --cacheinfo "$mode,$blob,.gitmodules"
    rm -f "$temp_dir/.gitmodules"
    rmdir "$temp_dir"
}

cmd_init() {
    local target_arg="" method=submodule url="$DEFAULT_URL" ref="" stage=no
    local url_set=no ref_set=no initialized_existing=no
    local module_gitdir="" module_gitdir_existed=no
    while [ $# -gt 0 ]; do
        case "$1" in
            --method) need_value "$@"; method="$2"; shift 2 ;;
            --url) need_value "$@"; url="$2"; url_set=yes; shift 2 ;;
            --ref) need_value "$@"; ref="$2"; ref_set=yes; shift 2 ;;
            --stage) stage=yes; shift ;;
            --*) die "unknown option: $1" ;;
            *) [ -z "$target_arg" ] || die "unexpected argument: $1"; target_arg="$1"; shift ;;
        esac
    done
    validate_method "$method"
    [ -n "$target_arg" ] || die "missing <target-repo>"
    [ -n "$url" ] && [[ "$url" != -* ]] || die "invalid submodule URL"
    [ -z "$ref" ] || [[ "$ref" != -* ]] || die "invalid ref: $ref"
    if [ "$method" = symlink ]; then
        [ "$url_set" = no ] || die "--url is only valid with --method submodule"
        [ "$ref_set" = no ] || die "--ref is only valid with --method submodule"
    fi
    canonical_repo "$target_arg"
    preflight_gitignore "$TARGET"
    preflight_gitmodules "$TARGET"
    preflight_anchor_parent "$TARGET"
    if [ "$method" = symlink ]; then
        require_planned_ignore "$TARGET" anchor:symlink "$ANCHOR_REL" \
            "/$ANCHOR_REL"
    fi
    inspect_anchor "$TARGET"
    if [ "$ANCHOR_HEALTH" = uninitialized ]; then
        [ "$method" = submodule ] \
            || die "existing anchor uses submodule, not $method"
        local registered_url="$SUBMODULE_URL"
        if [ "$url_set" = yes ] && [ "$registered_url" != "$url" ]; then
            die "existing submodule URL is '$registered_url', not requested '$url'"
        fi
        module_gitdir="$(git -C "$TARGET" rev-parse \
            --git-path "modules/$SUBMODULE_NAME")"
        case "$module_gitdir" in /*) ;; *) module_gitdir="$TARGET/$module_gitdir" ;; esac
        [ ! -e "$module_gitdir" ] || module_gitdir_existed=yes
        if ! git -c protocol.file.allow=always -C "$TARGET" \
            submodule update --init -- "$ANCHOR_REL"; then
            rollback_initialized_submodule "$TARGET" "$module_gitdir" \
                "$module_gitdir_existed"
            die "failed to initialize submodule at $ANCHOR_REL"
        fi
        initialized_existing=yes
        inspect_anchor "$TARGET"
        [ "$ANCHOR_HEALTH" = healthy ] \
            || die "initialized submodule is not healthy: $ANCHOR_REL"
    fi
    if [ "$ANCHOR_HEALTH" = healthy ]; then
        [ "$ANCHOR_MODE" = "$method" ] \
            || die "existing anchor uses $ANCHOR_MODE, not $method"
        if [ "$method" = symlink ]; then
            ensure_anchor_ignore "$TARGET"
        else
            local registered_url
            registered_url="$(git -C "$TARGET" config -f .gitmodules \
                --get-regexp '^submodule\..*\.url$' 2>/dev/null \
                | while read -r key value; do
                    path_key="${key%.url}.path"
                    path="$(git -C "$TARGET" config -f .gitmodules --get "$path_key")"
                    [ "$path" = "$ANCHOR_REL" ] && { printf '%s\n' "$value"; break; }
                done)"
            if [ "$url_set" = yes ] && [ "$registered_url" != "$url" ]; then
                die "existing submodule URL is '$registered_url', not requested '$url'"
            fi
            if [ "$ref_set" = yes ]; then
                [ -z "$(git -C "$TARGET/$ANCHOR_REL" status --porcelain)" ] \
                    || die "refusing to checkout --ref in dirty submodule"
                if ! git -C "$TARGET/$ANCHOR_REL" checkout "$ref"; then
                    if [ "$initialized_existing" = yes ]; then
                        rollback_initialized_submodule "$TARGET" "$module_gitdir" \
                            "$module_gitdir_existed"
                    fi
                    die "submodule ref not found: $ref"
                fi
            fi
            set_ignore_block "$TARGET" anchor:symlink
        fi
        printf 'Anchor already healthy: %s (%s)\n' "$ANCHOR_REL" "$method"
    elif [ "$ANCHOR_MODE" != missing ]; then
        die "refusing to replace $ANCHOR_HEALTH anchor: $TARGET/$ANCHOR_REL"
    else
        mkdir -p "$TARGET/.ai"
        if [ "$method" = symlink ]; then
            ln -s "$SKILLZ_ROOT" "$TARGET/$ANCHOR_REL"
            ensure_anchor_ignore "$TARGET"
        else
            local gitmodules_backup had_gitmodules=no
            gitmodules_backup="$(mktemp "${TMPDIR:-/tmp}/ai-skillz-gitmodules.XXXXXX")"
            if [ -f "$TARGET/.gitmodules" ]; then
                cp "$TARGET/.gitmodules" "$gitmodules_backup"
                had_gitmodules=yes
            fi
            if ! add_submodule_without_staging "$TARGET" "$url"; then
                rollback_new_submodule "$TARGET" "$gitmodules_backup" "$had_gitmodules"
                rm -f "$gitmodules_backup"
                die "failed to add submodule at $ANCHOR_REL"
            fi
            if [ "$ref_set" = yes ]; then
                if ! git -C "$TARGET/$ANCHOR_REL" checkout "$ref"; then
                    rollback_new_submodule "$TARGET" "$gitmodules_backup" "$had_gitmodules"
                    rm -f "$gitmodules_backup"
                    die "submodule ref not found: $ref"
                fi
            fi
            rm -f "$gitmodules_backup"
            set_ignore_block "$TARGET" anchor:symlink
        fi
        printf 'Created %s anchor at %s\n' "$method" "$TARGET/$ANCHOR_REL"
    fi
    if [ "$stage" = yes ]; then
        if [ "$method" = submodule ]; then
            stage_submodule_registration "$TARGET" "$ANCHOR_REL"
            local anchor_commit
            anchor_commit="$(git -C "$TARGET/$ANCHOR_REL" rev-parse HEAD)"
            git -C "$TARGET" update-index --add --cacheinfo \
                "160000,$anchor_commit,$ANCHOR_REL"
        else
            stage_paths "$TARGET" yes .gitignore
        fi
    fi
    stage_ignore_changes "$TARGET" "$stage"
}

cmd_update() {
    local target_arg="" ref="" stage=no anchor_rel="$ANCHOR_REL"
    while [ $# -gt 0 ]; do
        case "$1" in
            --ref) need_value "$@"; ref="$2"; shift 2 ;;
            --stage) stage=yes; shift ;;
            --*) die "unknown option: $1" ;;
            *) [ -z "$target_arg" ] || die "unexpected argument: $1"; target_arg="$1"; shift ;;
        esac
    done
    [ -n "$target_arg" ] || die "missing <target-repo>"
    [ -z "$ref" ] || [[ "$ref" != -* ]] || die "invalid ref: $ref"
    canonical_repo "$target_arg"
    inspect_anchor "$TARGET"
    if [ "$ANCHOR_HEALTH" = missing ] && [ -e "$TARGET/.claude/ai.skillz" ]; then
        anchor_rel=.claude/ai.skillz
        printf 'Warning: updating legacy anchor at %s\n' "$anchor_rel" >&2
        if [ -L "$TARGET/$anchor_rel" ]; then
            ANCHOR_MODE=symlink
            ANCHOR_HEALTH=healthy
            ANCHOR_SOURCE="$(cd "$TARGET/$anchor_rel" && pwd -P)"
        elif [ -f "$TARGET/$anchor_rel/.git" ]; then
            ANCHOR_MODE=submodule
            ANCHOR_HEALTH=healthy
        else
            die "legacy anchor is not an updateable symlink or submodule"
        fi
    fi
    [ "$ANCHOR_HEALTH" = healthy ] || die "no healthy ai.skillz anchor"
    if [ "$ANCHOR_MODE" = symlink ]; then
        [ -z "$ref" ] || die "cannot checkout --ref on a symlink anchor"
        printf 'Local symlink anchor already follows %s\n' "$ANCHOR_SOURCE"
        return 0
    fi
    [ -z "$(git -C "$TARGET/$anchor_rel" status --porcelain)" ] \
        || die "refusing to update dirty submodule: $anchor_rel"
    if [ -n "$ref" ]; then
        git -C "$TARGET/$anchor_rel" fetch origin
        git -C "$TARGET/$anchor_rel" checkout "$ref"
    else
        git -C "$TARGET/$anchor_rel" fetch origin
        git -C "$TARGET/$anchor_rel" merge --ff-only FETCH_HEAD
    fi
    stage_paths "$TARGET" "$stage" "$anchor_rel"
    printf 'Updated submodule at %s\n' "$anchor_rel"
}

same_resolved_path() {
    local left="$1" right="$2" left_resolved right_resolved
    resolve_existing_path "$left" || return 1
    left_resolved="$RESOLVED_PATH"
    resolve_existing_path "$right" || return 1
    right_resolved="$RESOLVED_PATH"
    [ "$left_resolved" = "$right_resolved" ]
}

skill_deployment_healthy() {
    local target="$1" provider="$2" skill="$3" shape assets dependency
    local asset destination source
    source="$SOURCE_ROOT/skills/$skill"
    get_skill_record "$skill" || return 1
    shape="$SKILL_SHAPE"
    assets="$SKILL_ASSETS"
    dependency="$SKILL_DEPENDENCY"
    [ "$shape" != template ] || return 1
    if [ -n "$dependency" ] && [ "$dependency" != - ]; then
        skill_deployment_healthy "$target" "$provider" "$dependency" \
            || return 1
    fi
    provider_root "$provider"
    destination="$target/$PROVIDER_ROOT/skills/$skill"
    if [ "$provider" = opencode ] \
        && self_hosted_skill_healthy "$target" "$skill"; then
        return 0
    fi
    if [ "$shape" = generic ]; then
        [ -L "$destination" ] && [ -f "$source/SKILL.md" ] \
            && same_resolved_path "$destination" "$source"
        return
    fi
    [ -d "$destination" ] && [ ! -L "$destination" ] || return 1
    IFS=',' read -ra ASSET_LIST <<< "$assets"
    for asset in "${ASSET_LIST[@]}"; do
        [ -L "$destination/$asset" ] && [ -e "$source/$asset" ] \
            && same_resolved_path "$destination/$asset" "$source/$asset" \
            || return 1
    done
    return 0
}

command_destination_manageable() {
    local source="$1" destination="$2" mode="$3" source_root="$4" source_rel="$5"
    if [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
        return 0
    fi
    if [ "$mode" = link ]; then
        if [ -L "$destination" ]; then
            same_resolved_path "$destination" "$source"
        elif [ -f "$destination" ]; then
            is_known_command_copy "$destination" "$source_root" "$source_rel"
        else
            return 1
        fi
        return
    fi
    if [ -L "$destination" ]; then
        same_resolved_path "$destination" "$source"
    elif [ -f "$destination" ]; then
        is_known_command_copy "$destination" "$source_root" "$source_rel"
    else
        return 1
    fi
}

providers_include_opencode() {
    local selected_provider
    for selected_provider in "${PROVIDERS[@]}"; do
        [ "$selected_provider" = opencode ] && return 0
    done
    return 1
}

collect_skill_command_jobs() {
    local wanted_skill="$1" kind provider name source mode dependency rest
    while IFS='|' read -r kind provider name source mode dependency rest; do
        [ "$kind" = command ] || continue
        [ "$provider" = opencode ] || continue
        [ "$dependency" = "$wanted_skill" ] || continue
        COMMAND_JOBS+=("$provider:$name")
    done < "$MANIFEST"
}

preflight_command_job() {
    local job="$1" direct="$2" global="$3" planned_dependency="$4"
    local job_provider="${job%%:*}" job_name="${job#*:}" destination
    get_command_record "$job_provider" "$job_name" \
        || die "manifest command disappeared"
    [ -f "$SOURCE_ROOT/$COMMAND_SOURCE" ] \
        || die "command source missing from deployment source: $SOURCE_ROOT/$COMMAND_SOURCE"
    if [ "$global" = no ] && [ "$COMMAND_SKILL" != - ] \
        && [ "$planned_dependency" != '*' ] \
        && [ "$COMMAND_SKILL" != "$planned_dependency" ]; then
        skill_deployment_healthy "$TARGET" "$job_provider" "$COMMAND_SKILL" \
            || die "command '$job_name' requires healthy $job_provider skill '$COMMAND_SKILL'"
    fi
    [ "$global" = yes ] || preflight_runtime_ignores "$job_name" "$TARGET"
    provider_root "$job_provider"
    if [ "$global" = yes ]; then
        destination="$HOME/.claude/commands/$job_name.md"
    else
        preflight_directory_chain "$TARGET" "$PROVIDER_ROOT/commands"
        destination="$TARGET/$PROVIDER_ROOT/commands/$job_name.md"
        if [ "$direct" = yes ]; then
            require_planned_ignore "$TARGET" \
                "direct:symlink:$job_provider:command:$job_name" \
                "$PROVIDER_ROOT/commands/$job_name.md" \
                "/$PROVIDER_ROOT/commands/$job_name.md"
            require_local_path_untracked "$TARGET" \
                "$PROVIDER_ROOT/commands/$job_name.md"
        else
            require_portable_path_trackable "$TARGET" \
                "$PROVIDER_ROOT/commands/$job_name.md"
        fi
    fi
    command_destination_manageable \
        "$SOURCE_ROOT/$COMMAND_SOURCE" "$destination" \
        "$COMMAND_MODE" "$SOURCE_ROOT" "$COMMAND_SOURCE" \
        || die "refusing unmanaged command destination: $destination"
}

deploy_command_jobs() {
    local target="$1" direct="$2" global="$3" job job_provider job_name
    COMMAND_DEPLOYED=0
    for job in "${COMMAND_JOBS[@]}"; do
        job_provider="${job%%:*}"
        job_name="${job#*:}"
        deploy_command_provider \
            "$job_name" "$target" "$job_provider" "$direct" "$global"
        COMMAND_DEPLOYED=$((COMMAND_DEPLOYED + 1))
    done
}

report_companion_hook() {
    local source="$1" target_label="$2" hook
    for hook in "$(dirname "$source")"/*.hook.json; do
        [ -f "$hook" ] || continue
        printf '\nCompanion hook (manual settings merge):\n'
        printf '  %s\n' "$hook"
        printf '  into %s (under the "hooks" key)\n' "$target_label"
        break
    done
}

deploy_command_provider() {
    local name="$1" target="$2" provider="$3" direct="$4" global="$5"
    get_command_record "$provider" "$name" || return 1
    local source="$SOURCE_ROOT/$COMMAND_SOURCE"
    [ -f "$source" ] || die "command source missing from deployment source: $source"
    provider_root "$provider"
    local destination
    if [ "$global" = yes ]; then
        destination="$HOME/.claude/commands/$name.md"
    else
        destination="$target/$PROVIDER_ROOT/commands/$name.md"
    fi
    mkdir -p "$(dirname "$destination")"
    if [ "$COMMAND_MODE" = copy ]; then
        if [ -L "$destination" ] && [ "$target" = "$SOURCE_ROOT" ] \
            && same_resolved_path "$destination" "$source"; then
            printf 'Preserved command %s as an intentional source-repo symlink\n' "$name"
        else
            atomic_copy "$source" "$destination" "$SOURCE_ROOT" "$COMMAND_SOURCE"
        fi
        [ "$global" = yes ] \
            || set_ignore_block "$target" "direct:symlink:$provider:command:$name"
    elif [ "$direct" = yes ] || [ "$global" = yes ]; then
        if [ "$global" = no ] && [ "$target" = "$SOURCE_ROOT" ] \
            && [ -L "$destination" ] \
            && git_path_tracked "$target" "$PROVIDER_ROOT/commands/$name.md" \
            && same_resolved_path "$destination" "$source"; then
            set_ignore_block "$target" "direct:symlink:$provider:command:$name"
            ensure_runtime_ignores "$name" "$target"
            record_managed_path "$PROVIDER_ROOT/commands/$name.md"
            printf 'Preserved command %s as an intentional source-repo symlink\n' "$name"
            return 0
        fi
        if [ -f "$destination" ] && [ ! -L "$destination" ]; then
            is_known_command_copy "$destination" "$SOURCE_ROOT" "$COMMAND_SOURCE" \
                || die "refusing to replace user-authored command file: $destination"
            rm "$destination"
        fi
        safe_link "$source" "$destination" "$source"
        [ "$global" = yes ] \
            || set_ignore_block "$target" "direct:symlink:$provider:command:$name" \
                "/$PROVIDER_ROOT/commands/$name.md"
        [ "$global" = yes ] \
            || require_effective_ignore "$target" "$PROVIDER_ROOT/commands/$name.md"
    else
        if [ -f "$destination" ] && [ ! -L "$destination" ]; then
            is_known_command_copy "$destination" "$SOURCE_ROOT" "$COMMAND_SOURCE" \
                || die "refusing to replace user-authored command file: $destination"
            rm "$destination"
        fi
        safe_link "../../$ANCHOR_REL/$COMMAND_SOURCE" "$destination" "$source"
        set_ignore_block "$target" "direct:symlink:$provider:command:$name"
    fi
    if [ "$global" = no ]; then
        ensure_runtime_ignores "$name" "$target"
        record_managed_path "$PROVIDER_ROOT/commands/$name.md"
    fi
    printf 'Deployed command %s to %s (%s)\n' "$name" \
        "$([ "$global" = yes ] && printf '~/.claude' || printf '%s' "$PROVIDER_ROOT")" \
        "$COMMAND_MODE"
    if [ "$provider" = claude ]; then
        if [ "$global" = yes ]; then
            report_companion_hook "$source" '~/.claude/settings.json'
        else
            report_companion_hook "$source" "$target/.claude/settings.json"
        fi
    fi
}

deploy_command() {
    local name="" target_arg="" provider=claude method="" direct=no stage=no global=no
    while [ $# -gt 0 ]; do
        case "$1" in
            --provider) need_value "$@"; provider="$2"; shift 2 ;;
            --method) need_value "$@"; method="$2"; shift 2 ;;
            --direct) direct=yes; shift ;;
            --stage) stage=yes; shift ;;
            --global) global=yes; shift ;;
            --*) die "unknown option: $1" ;;
            *)
                if [ -z "$name" ]; then name="$1"; shift
                elif [ -z "$target_arg" ]; then target_arg="$1"; shift
                else die "unexpected argument: $1"
                fi
                ;;
        esac
    done
    [ -n "$name" ] || die "missing <command-name>"
    [ "$name" = all ] || validate_name "$name" command
    validate_provider "$provider"
    [ -z "$method" ] || validate_method "$method"
    if [ "$global" = yes ]; then
        [ -z "$target_arg" ] || die "--global does not accept a target repository"
        [ "$stage" = no ] || die "--stage is invalid with --global"
        [ -z "$method" ] || [ "$method" = symlink ] \
            || die "--global supports only --method symlink"
        [ "$provider" != opencode ] || die "--global is supported only for Claude commands"
        TARGET=""
        SOURCE_ROOT="$SKILLZ_ROOT"
        direct=yes
    else
        [ -n "$target_arg" ] || die "missing <target-repo>"
        canonical_repo "$target_arg"
        preflight_gitignore "$TARGET"
        select_deployment_source "$TARGET" "$method" "$direct"
        direct="$DEPLOY_DIRECT"
    fi
    set_providers "$provider"

    local selected_provider kind manifest_provider manifest_name source mode dependency rest
    local count=0 skipped=0 job
    COMMAND_JOBS=()
    if [ "$name" = all ]; then
        while IFS='|' read -r kind manifest_provider manifest_name source mode dependency rest; do
            [ "$kind" = command ] || continue
            for selected_provider in "${PROVIDERS[@]}"; do
                [ "$manifest_provider" = "$selected_provider" ] || continue
                [ "$global" = no ] || [ "$selected_provider" = claude ] || continue
                COMMAND_JOBS+=("$selected_provider:$manifest_name")
            done
        done < "$MANIFEST"
    else
        for selected_provider in "${PROVIDERS[@]}"; do
            if get_command_record "$selected_provider" "$name"; then
                if [ "$global" = yes ] && [ "$selected_provider" != claude ]; then
                    printf 'SKIP command %s for %s (global Claude-only)\n' "$name" "$selected_provider"
                    skipped=$((skipped + 1))
                else
                    COMMAND_JOBS+=("$selected_provider:$name")
                fi
            else
                printf 'SKIP command %s for %s (unsupported)\n' "$name" "$selected_provider"
                skipped=$((skipped + 1))
            fi
        done
    fi
    [ ${#COMMAND_JOBS[@]} -gt 0 ] || die "command '$name' is unsupported by selected provider(s)"

    # Preflight every selected job before writing any provider destination.
    for job in "${COMMAND_JOBS[@]}"; do
        preflight_command_job "$job" "$direct" "$global" ''
    done

    MANAGED_PATHS=()
    deploy_command_jobs "$TARGET" "$direct" "$global"
    count="$COMMAND_DEPLOYED"
    if [ "$global" = no ]; then
        stage_paths "$TARGET" "$stage" "${MANAGED_PATHS[@]}"
        stage_ignore_changes "$TARGET" "$stage"
    fi
    printf 'Result: %d command deployment(s), %d unsupported skipped\n' "$count" "$skipped"
}

link_description() {
    local path="$1" expected="$2"
    LINK_HEALTH=healthy
    if [ ! -L "$path" ]; then
        if [ -e "$path" ]; then
            LINK_DESCRIPTION="not a symlink"
        else
            LINK_DESCRIPTION="missing"
        fi
        LINK_HEALTH=unhealthy
        return
    fi
    local value
    value="$(readlink "$path")"
    if [ ! -e "$path" ]; then
        LINK_DESCRIPTION="broken -> $value"
        LINK_HEALTH=unhealthy
    elif [[ "$value" = /* ]]; then
        LINK_DESCRIPTION="local-only (absolute) -> $value"
    elif [ "$value" = "$expected" ]; then
        LINK_DESCRIPTION="portable (relative) -> $value"
    elif [[ "$value" = *ai.skillz/skills/* ]]; then
        local resolved legacy_root
        resolved=""
        if resolve_existing_path "$path"; then
            resolved="$RESOLVED_PATH"
        fi
        legacy_root="${resolved%%/skills/*}"
        if [ -n "$resolved" ] \
            && [ -f "$legacy_root/deploy-manifest.conf" ]; then
            LINK_DESCRIPTION="legacy (relative) -> $value"
        else
            LINK_DESCRIPTION="unexpected relative -> $value"
            LINK_HEALTH=unhealthy
        fi
    else
        LINK_DESCRIPTION="unexpected relative -> $value"
        LINK_HEALTH=unhealthy
    fi
}

runtime_local_entry_allowed() {
    local skill="$1" entry="$2" section="" line prefix remainder name
    prefix=".claude/skills/$skill/"
    name="$(basename "$entry")"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi
        [ "$section" = "$skill" ] || continue
        case "$line" in "$prefix"*) ;; *) continue ;; esac
        remainder="${line#$prefix}"
        remainder="${remainder%/}"
        [ "$remainder" = "$name" ] || continue
        if [[ "$line" = */ ]]; then
            [ -d "$entry" ] && [ ! -L "$entry" ] && return 0
        else
            [ -f "$entry" ] && [ ! -L "$entry" ] && return 0
        fi
    done < "$PATTERNS_CONF"
    return 1
}

hybrid_runtime_state_only() {
    local path="$1" skill="$2" entry
    for entry in "$path"/* "$path"/.[!.]* "$path"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        runtime_local_entry_allowed "$skill" "$entry" || return 1
    done
    return 0
}

run_tests_harness_only() {
    local path="$1" entry found=no
    for entry in "$path"/* "$path"/.[!.]* "$path"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        [ "$(basename "$entry")" = test-harness-reference.md ] \
            && [ -f "$entry" ] && [ ! -L "$entry" ] \
            || return 1
        found=yes
    done
    [ "$found" = yes ]
}

record_status_direct_root() {
    local candidate="$1"
    if [ -z "${STATUS_DIRECT_ROOT:-}" ]; then
        STATUS_DIRECT_ROOT="$candidate"
        return 0
    fi
    [ "$STATUS_DIRECT_ROOT" = "$candidate" ]
}

runtime_owner_enabled() {
    local target="$1" name="$2"
    [ -e "$target/.claude/skills/$name" ] \
        || [ -L "$target/.claude/skills/$name" ] \
        || [ -e "$target/.opencode/skills/$name" ] \
        || [ -L "$target/.opencode/skills/$name" ] \
        || [ -e "$target/.claude/commands/$name.md" ] \
        || [ -L "$target/.claude/commands/$name.md" ] \
        || [ -e "$target/.opencode/commands/$name.md" ] \
        || [ -L "$target/.opencode/commands/$name.md" ]
}

status_runtime_ignores() {
    local target="$1" section="" line relative
    [ -f "$PATTERNS_CONF" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi
        [ -n "$section" ] && [ -n "$line" ] \
            && runtime_owner_enabled "$target" "$section" || continue
        relative="${line#/}"
        if ! path_effectively_ignored "$target" "$relative"; then
            printf 'Runtime %-24s %s [UNHEALTHY:not ignored]\n' \
                "$section" "$relative"
            STATUS_UNHEALTHY=1
        fi
    done < "$PATTERNS_CONF"
}

status_provider() {
    local target="$1" provider="$2"
    provider_root "$provider"
    local root="$target/$PROVIDER_ROOT" kind name shape assets dependency
    local rest path asset
    local canonical_asset_present
    if [ ! -d "$root" ]; then
        printf 'Provider %s: disabled\n' "$provider"
        return 0
    fi
    printf 'Provider %s: enabled\n' "$provider"
    while IFS='|' read -r kind name shape assets dependency rest; do
        [ "$kind" = skill ] || continue
        path="$root/skills/$name"
        if [ "$shape" = template ]; then
            if [ -e "$path" ] || [ -L "$path" ]; then
                if [ -d "$path" ] && [ ! -L "$path" ] \
                    && [ -f "$path/SKILL.md" ] && [ ! -L "$path/SKILL.md" ] \
                    && grep -q "^name:[[:space:]]*$name[[:space:]]*$" "$path/SKILL.md"; then
                    printf '  skill %-24s local template [healthy]\n' "$name"
                else
                    printf '  skill %-24s invalid generated template [UNHEALTHY]\n' "$name"
                    STATUS_UNHEALTHY=1
                fi
            fi
            continue
        fi
        [ -e "$path" ] || [ -L "$path" ] || continue
        if [ "$shape" = generic ]; then
            relative_skill_target generic "$name"
            link_description "$path" "$LINK_TARGET"
            printf '  skill %-24s %s' "$name" "$LINK_DESCRIPTION"
            tracking_description "$target" "$PROVIDER_ROOT/skills/$name"
            printf ' [%s]' "$TRACKING"
            [ "$LINK_HEALTH" = healthy ] || { printf ' [UNHEALTHY]'; STATUS_UNHEALTHY=1; }
            if [[ "$(readlink "$path" 2>/dev/null || true)" != /* ]] \
                && [ "$TRACKING" = ignored ]; then
                printf ' [UNHEALTHY:portable link ignored]'
                STATUS_UNHEALTHY=1
            fi
            if [ "$ANCHOR_HEALTH" = healthy ] \
                && ! same_resolved_path "$path" "$SOURCE_ROOT/skills/$name"; then
                printf ' [UNHEALTHY:not sourced from anchor]'
                STATUS_UNHEALTHY=1
            fi
            if [ "$LINK_HEALTH" = healthy ]; then
                if ! recognized_source_root "$path" "$name" ""; then
                    printf ' [UNHEALTHY:unrecognized source]'
                    STATUS_UNHEALTHY=1
                elif ! record_status_direct_root "$RECOGNIZED_ROOT"; then
                    printf ' [UNHEALTHY:mixed source roots]'
                    STATUS_UNHEALTHY=1
                fi
            fi
            if [[ "$(readlink "$path" 2>/dev/null || true)" = /* ]]; then
                if [ "$TRACKING" != ignored ]; then
                    printf ' [UNHEALTHY:absolute link not ignored]'
                    STATUS_UNHEALTHY=1
                fi
            fi
            printf '\n'
        else
            if [ -L "$path" ] || [ ! -d "$path" ]; then
                printf '  skill %-24s invalid hybrid directory [UNHEALTHY]\n' "$name"
                STATUS_UNHEALTHY=1
                continue
            fi
            IFS=',' read -ra ASSET_LIST <<< "$assets"
            canonical_asset_present=no
            for asset in "${ASSET_LIST[@]}"; do
                if [ -e "$path/$asset" ] || [ -L "$path/$asset" ]; then
                    canonical_asset_present=yes
                    break
                fi
            done
            if [ "$canonical_asset_present" = no ] && [ "$provider" = claude ] \
                && { hybrid_runtime_state_only "$path" "$name" \
                    || { [ "$name" = run-tests ] \
                        && run_tests_harness_only "$path"; }; }; then
                printf '  skill %-24s runtime-state-only (not deployed) [healthy]\n' "$name"
                continue
            fi
            for asset in "${ASSET_LIST[@]}"; do
                relative_skill_target hybrid "$name" "$asset"
                link_description "$path/$asset" "$LINK_TARGET"
                printf '  skill %-24s %s: %s' "$name" "$asset" "$LINK_DESCRIPTION"
                tracking_description "$target" "$PROVIDER_ROOT/skills/$name/$asset"
                printf ' [%s]' "$TRACKING"
                [ "$LINK_HEALTH" = healthy ] || { printf ' [UNHEALTHY]'; STATUS_UNHEALTHY=1; }
                if [[ "$(readlink "$path/$asset" 2>/dev/null || true)" != /* ]] \
                    && [ "$TRACKING" = ignored ]; then
                    printf ' [UNHEALTHY:portable link ignored]'
                    STATUS_UNHEALTHY=1
                fi
                if [ "$ANCHOR_HEALTH" = healthy ] \
                    && ! same_resolved_path "$path/$asset" \
                        "$SOURCE_ROOT/skills/$name/$asset"; then
                    printf ' [UNHEALTHY:not sourced from anchor]'
                    STATUS_UNHEALTHY=1
                fi
                if [ "$LINK_HEALTH" = healthy ]; then
                    if ! recognized_source_root "$path/$asset" "$name" "$asset"; then
                        printf ' [UNHEALTHY:unrecognized source]'
                        STATUS_UNHEALTHY=1
                    elif ! record_status_direct_root "$RECOGNIZED_ROOT"; then
                        printf ' [UNHEALTHY:mixed source roots]'
                        STATUS_UNHEALTHY=1
                    fi
                fi
                if [[ "$(readlink "$path/$asset" 2>/dev/null || true)" = /* ]] \
                    && [ "$TRACKING" != ignored ]; then
                    printf ' [UNHEALTHY:absolute link not ignored]'
                    STATUS_UNHEALTHY=1
                fi
                printf '\n'
            done
        fi
        if [ -n "$dependency" ] && [ "$dependency" != - ] \
            && ! skill_deployment_healthy \
                "$target" "$provider" "$dependency"; then
            printf '  skill %-24s dependency %s missing or unhealthy [UNHEALTHY]\n' \
                "$name" "$dependency"
            STATUS_UNHEALTHY=1
        fi
    done < "$MANIFEST"

    local manifest_provider source mode dependency command_path source_path
    while IFS='|' read -r kind manifest_provider name source mode dependency rest; do
        [ "$kind" = command ] && [ "$manifest_provider" = "$provider" ] || continue
        command_path="$root/commands/$name.md"
        if [ ! -e "$command_path" ] && [ ! -L "$command_path" ]; then
            printf '  command %-22s missing\n' "$name"
            continue
        fi
        source_path="$SOURCE_ROOT/$source"
        if [ -L "$command_path" ] && [ "$target" = "$SOURCE_ROOT" ] \
            && [ -f "$source_path" ] && same_resolved_path "$command_path" "$source_path"; then
            tracking_description "$target" "$PROVIDER_ROOT/commands/$name.md"
            printf '  command %-22s intentional source-repo symlink [healthy] [%s]\n' \
                "$name" "$TRACKING"
        elif [ "$mode" = link ]; then
            link_description "$command_path" "../../$ANCHOR_REL/$source"
            printf '  command %-22s %s' "$name" "$LINK_DESCRIPTION"
            tracking_description "$target" "$PROVIDER_ROOT/commands/$name.md"
            printf ' [%s]' "$TRACKING"
            [ "$LINK_HEALTH" = healthy ] || { printf ' [UNHEALTHY]'; STATUS_UNHEALTHY=1; }
            if [[ "$(readlink "$command_path" 2>/dev/null || true)" != /* ]] \
                && [ "$TRACKING" = ignored ]; then
                printf ' [UNHEALTHY:portable link ignored]'
                STATUS_UNHEALTHY=1
            fi
            if [ "$ANCHOR_HEALTH" = healthy ] \
                && ! same_resolved_path "$command_path" "$source_path"; then
                printf ' [UNHEALTHY:not sourced from anchor]'
                STATUS_UNHEALTHY=1
            fi
            if [ "$LINK_HEALTH" = healthy ]; then
                if ! recognized_command_root "$command_path" "$provider" "$name" \
                    "$source"; then
                    printf ' [UNHEALTHY:unrecognized source]'
                    STATUS_UNHEALTHY=1
                elif ! record_status_direct_root "$RECOGNIZED_ROOT"; then
                    printf ' [UNHEALTHY:mixed source roots]'
                    STATUS_UNHEALTHY=1
                fi
            fi
            if [[ "$(readlink "$command_path" 2>/dev/null || true)" = /* ]] \
                && [ "$TRACKING" != ignored ]; then
                printf ' [UNHEALTHY:absolute link not ignored]'
                STATUS_UNHEALTHY=1
            fi
            printf '\n'
        elif [ -f "$source_path" ] && [ ! -L "$command_path" ] \
            && cmp -s "$source_path" "$command_path"; then
            tracking_description "$target" "$PROVIDER_ROOT/commands/$name.md"
            printf '  command %-22s copied [healthy] [%s]' "$name" "$TRACKING"
            if [ "$TRACKING" = ignored ]; then
                printf ' [UNHEALTHY:copied command ignored]'
                STATUS_UNHEALTHY=1
            fi
            printf '\n'
        else
            printf '  command %-22s copied content differs [UNHEALTHY]\n' "$name"
            STATUS_UNHEALTHY=1
        fi
        if [ "$dependency" != - ] \
            && ! skill_deployment_healthy "$target" "$provider" "$dependency"; then
            printf '  command %-22s dependency skill %s missing or unhealthy [UNHEALTHY]\n' \
                "$name" "$dependency"
            STATUS_UNHEALTHY=1
        fi
    done < "$MANIFEST"
}

extract_skill_paths_fallback() {
    local file="$1" compact body value
    compact="$(tr '\n' ' ' < "$file")"
    CONFIG_PATHS=()
    if [[ "$compact" =~ \"skills\"[[:space:]]*:[[:space:]]*\{[^\}]*\"paths\"[[:space:]]*:[[:space:]]*\[([^\]]*)\] ]]; then
        body="${BASH_REMATCH[1]}"
        while [[ "$body" =~ \"([^\"]*)\" ]]; do
            value="${BASH_REMATCH[1]}"
            CONFIG_PATHS+=("$value")
            body="${body#*\"$value\"}"
        done
        CONFIG_PARSE_MODE=fallback
        return 0
    fi
    CONFIG_PARSE_MODE=uncertain
    return 1
}

extract_opencode_skill_paths() {
    local file="$1" output path
    CONFIG_PATHS=()
    CONFIG_PARSE_MODE=parsed
    if [ "${AI_SKILLZ_NO_PYTHON:-no}" != yes ] \
        && command -v python3 >/dev/null 2>&1; then
        if output="$(python3 -c '
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
if sys.argv[1].endswith(".jsonc"):
    out, i, string, escape = [], 0, False, False
    while i < len(text):
        char = text[i]
        if string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "\"":
                string = False
            i += 1
        elif char == "\"":
            string = True; out.append(char); i += 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0: break
            out.append("\n")
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0: raise ValueError("unterminated comment")
            i = end + 2
        else:
            out.append(char); i += 1
    text = re.sub(r",\s*([}\]])", r"\1", "".join(out))
data = json.loads(text)
skills = data.get("skills", {}) if isinstance(data, dict) else {}
paths = skills.get("paths", []) if isinstance(skills, dict) else []
if isinstance(paths, str): paths = [paths]
if isinstance(paths, list):
    for path in paths:
        if isinstance(path, str): print(path)
' "$file" 2>/dev/null)"; then
            while IFS= read -r path || [ -n "$path" ]; do
                [ -n "$path" ] && CONFIG_PATHS+=("$path")
            done <<EOF
$output
EOF
            return 0
        fi
        case "$file" in *.json) CONFIG_PARSE_MODE=invalid; return 1 ;; esac
    fi
    extract_skill_paths_fallback "$file"
}

self_hosted_skill_healthy() {
    local target="$1" skill="$2" config path resolved
    [ "$target" = "$SOURCE_ROOT" ] || return 1
    [ -f "$target/skills/$skill/SKILL.md" ] || return 1
    for config in .opencode/opencode.json .opencode/opencode.jsonc opencode.json opencode.jsonc; do
        [ -f "$target/$config" ] || continue
        extract_opencode_skill_paths "$target/$config" || continue
        for path in "${CONFIG_PATHS[@]}"; do
            case "$path" in skills|./skills)
                resolve_existing_path "$target/$path" || continue
                resolved="$RESOLVED_PATH"
                [ "$resolved" = "$target/skills" ] && return 0
                ;;
            esac
        done
    done
    return 1
}

inspect_opencode_config() {
    local target="$1" config="$2" path found=no
    if ! extract_opencode_skill_paths "$target/$config"; then
        if [ "$CONFIG_PARSE_MODE" = invalid ]; then
            printf 'Config: %s invalid JSON [UNHEALTHY]\n' "$config"
            STATUS_UNHEALTHY=1
        else
            printf 'Config: %s JSONC skills.paths inspection uncertain [UNHEALTHY]\n' "$config"
            STATUS_UNHEALTHY=1
        fi
        return 0
    fi
    for path in "${CONFIG_PATHS[@]}"; do
        if [[ "$path" = /* ]]; then
            printf 'Config: %s skills.paths contains absolute path: %s [UNHEALTHY]\n' \
                "$config" "$path"
            STATUS_UNHEALTHY=1
            found=yes
        fi
    done
    [ "$found" = yes ] || printf 'Config: %s inspected via %s (portable skills.paths)\n' \
        "$config" "$CONFIG_PARSE_MODE"
}

cmd_status() {
    local target_arg="" provider=all
    while [ $# -gt 0 ]; do
        case "$1" in
            --provider) need_value "$@"; provider="$2"; shift 2 ;;
            --*) die "unknown option: $1" ;;
            *) [ -z "$target_arg" ] || die "unexpected argument: $1"; target_arg="$1"; shift ;;
        esac
    done
    validate_provider "$provider"
    [ -n "$target_arg" ] || die "missing <target-repo>"
    canonical_repo "$target_arg"
    STATUS_UNHEALTHY=0
    STATUS_DIRECT_ROOT=""
    inspect_anchor "$TARGET"
    if [ "$ANCHOR_HEALTH" = healthy ]; then
        SOURCE_ROOT="$ANCHOR_SOURCE"
    else
        SOURCE_ROOT="$SKILLZ_ROOT"
    fi
    printf 'Target: %s\n' "$TARGET"
    case "$ANCHOR_HEALTH" in
        healthy)
            printf 'Anchor: %s (healthy, %s)' "$ANCHOR_MODE" "$ANCHOR_SOURCE"
            tracking_description "$TARGET" "$ANCHOR_REL"
            printf ' [%s]' "$TRACKING"
            if [ "$ANCHOR_MODE" = symlink ] && [ "$TRACKING" != ignored ]; then
                printf ' [UNHEALTHY:local anchor not ignored]'
                STATUS_UNHEALTHY=1
            fi
            printf '\n'
            ;;
        missing) printf 'Anchor: missing\n' ;;
        *) printf 'Anchor: %s [%s, UNHEALTHY]\n' "$ANCHOR_MODE" "$ANCHOR_HEALTH"; STATUS_UNHEALTHY=1 ;;
    esac
    if legacy_anchor_registered "$TARGET"; then
        printf 'Legacy anchor: .claude/ai.skillz detected [warning]\n'
    else
        printf 'Legacy anchor: none\n'
    fi
    set_providers "$provider"
    local selected_provider
    for selected_provider in "${PROVIDERS[@]}"; do
        status_provider "$TARGET" "$selected_provider"
    done
    status_runtime_ignores "$TARGET"
    local config
    for config in .opencode/opencode.json .opencode/opencode.jsonc opencode.json opencode.jsonc; do
        [ -f "$TARGET/$config" ] || continue
        inspect_opencode_config "$TARGET" "$config"
    done
    [ "$STATUS_UNHEALTHY" -eq 0 ] || return 1
}

manifest_has_skill() {
    local root="$1" wanted="$2" asset="$3"
    local kind name shape assets rest expected_shape="" expected_assets=""
    [ -f "$root/deploy-manifest.conf" ] || return 1
    while IFS='|' read -r kind name shape assets rest; do
        [ "$kind" = skill ] && [ "$name" = "$wanted" ] || continue
        expected_shape="$shape"
        expected_assets="$assets"
        break
    done < "$MANIFEST"
    [ -n "$expected_shape" ] || return 1
    while IFS='|' read -r kind name shape assets rest; do
        [ "$kind" = skill ] && [ "$name" = "$wanted" ] \
            && [ "$shape" = "$expected_shape" ] \
            && [ "$assets" = "$expected_assets" ] || continue
        [ -z "$asset" ] && return 0
        case ",$assets," in *",$asset,"*) return 0 ;; esac
    done < "$root/deploy-manifest.conf"
    return 1
}

manifest_has_command() {
    local root="$1" wanted_provider="$2" wanted_name="$3" wanted_source="$4"
    local kind provider name source mode dependency rest
    local expected_mode="" expected_dependency=""
    [ -f "$root/deploy-manifest.conf" ] || return 1
    while IFS='|' read -r kind provider name source mode dependency rest; do
        [ "$kind" = command ] && [ "$provider" = "$wanted_provider" ] \
            && [ "$name" = "$wanted_name" ] && [ "$source" = "$wanted_source" ] \
            || continue
        expected_mode="$mode"
        expected_dependency="$dependency"
        break
    done < "$MANIFEST"
    [ -n "$expected_mode" ] || return 1
    while IFS='|' read -r kind provider name source mode dependency rest; do
        [ "$kind" = command ] && [ "$provider" = "$wanted_provider" ] \
            && [ "$name" = "$wanted_name" ] && [ "$source" = "$wanted_source" ] \
            && [ "$mode" = "$expected_mode" ] \
            && [ "$dependency" = "$expected_dependency" ] && return 0
    done < "$root/deploy-manifest.conf"
    return 1
}

recognized_source_root() {
    local link_path="$1" skill="$2" asset="$3" resolved suffix
    RECOGNIZED_ROOT=""
    [ -L "$link_path" ] || return 1
    resolve_existing_path "$link_path" || return 1
    resolved="$RESOLVED_PATH"
    [ -n "$resolved" ] || return 1
    suffix="/skills/$skill"
    [ -n "$asset" ] && suffix="$suffix/$asset"
    [[ "$resolved" = *"$suffix" ]] || return 1
    RECOGNIZED_ROOT="${resolved%$suffix}"
    manifest_has_skill "$RECOGNIZED_ROOT" "$skill" "$asset"
}

recognized_command_root() {
    local link_path="$1" provider="$2" name="$3" source="$4" resolved suffix
    RECOGNIZED_ROOT=""
    [ -L "$link_path" ] || return 1
    resolve_existing_path "$link_path" || return 1
    resolved="$RESOLVED_PATH"
    [ -n "$resolved" ] || return 1
    suffix="/$source"
    [[ "$resolved" = *"$suffix" ]] || return 1
    RECOGNIZED_ROOT="${resolved%$suffix}"
    manifest_has_command "$RECOGNIZED_ROOT" "$provider" "$name" "$source"
}

migration_root_allowed() {
    local candidate="$1"
    [ "$candidate" = "$planned_source" ] && return 0
    [ "$ANCHOR_HEALTH" = healthy ] && [ "$ANCHOR_MODE" = submodule ] \
        || return 1
    if [ -z "$MIGRATE_LEGACY_ROOT" ]; then
        MIGRATE_LEGACY_ROOT="$candidate"
        return 0
    fi
    [ "$candidate" = "$MIGRATE_LEGACY_ROOT" ]
}

migration_action() {
    if [ "$MIGRATE_DRY_RUN" = yes ]; then
        printf 'Would %s\n' "$*"
    else
        printf '%s\n' "$*"
    fi
}

reconcile_migration_ignore() {
    local target="$1" index="$2" id
    id="${MIGRATE_IGNORE_IDS[$index]}"
    local i pattern provider name has_patterns=no
    local patterns=()
    i=0
    while [ "$i" -lt "${#MIGRATE_IGNORE_IDS[@]}" ]; do
        if [ "${MIGRATE_IGNORE_IDS[$i]}" = "$id" ] \
            && [ -n "${MIGRATE_IGNORE_PATTERNS[$i]}" ]; then
            has_patterns=yes
            break
        fi
        i=$((i + 1))
    done
    if [ "$has_patterns" = yes ]; then
        case "$id" in
            direct:symlink:*:command:*)
                provider="${id#direct:symlink:}"
                provider="${provider%%:*}"
                name="${id##*:command:}"
                provider_root "$provider"
                patterns+=("/$PROVIDER_ROOT/commands/$name.md")
                ;;
            direct:symlink:*:*)
                provider="${id#direct:symlink:}"
                provider="${provider%%:*}"
                name="${id##*:}"
                get_skill_record "$name" \
                    || die "migration skill disappeared from manifest: $name"
                direct_ignore_paths "$provider" "$name" "$SKILL_SHAPE" \
                    "$SKILL_ASSETS"
                patterns=("${DIRECT_PATTERNS[@]}")
                ;;
            *) die "unexpected migration ignore id: $id" ;;
        esac
    fi
    set_ignore_block "$target" "$id" "${patterns[@]}"
    for pattern in "${patterns[@]}"; do
        require_effective_ignore "$target" "${pattern#/}"
    done
}

get_submodule_registration() {
    local target="$1" wanted_path="$2" records key path name
    SUBMODULE_NAME=""
    SUBMODULE_URL=""
    [ -f "$target/.gitmodules" ] || return 1
    records="$(git -C "$target" config -f .gitmodules \
        --get-regexp '^submodule\..*\.path$' 2>/dev/null || true)"
    while IFS=' ' read -r key path; do
        [ "$path" = "$wanted_path" ] || continue
        name="${key#submodule.}"
        name="${name%.path}"
        SUBMODULE_NAME="$name"
        SUBMODULE_URL="$(git -C "$target" config -f .gitmodules \
            --get "submodule.$name.url")"
        return 0
    done <<EOF
$records
EOF
    return 1
}

validate_legacy_submodule_move() {
    local target="$1" legacy
    legacy="$target/.claude/ai.skillz"
    [ -f "$legacy/.git" ] || die "legacy submodule checkout is missing or invalid"
    get_submodule_registration "$target" .claude/ai.skillz \
        || die "legacy submodule is not registered in .gitmodules"
    [ -n "$SUBMODULE_URL" ] || die "legacy submodule URL is empty"
    [ -z "$(git -C "$legacy" status --porcelain)" ] \
        || die "refusing to relocate dirty legacy submodule"
    if git -C "$legacy" ls-files -s | grep -q '^160000 '; then
        die "refusing to relocate legacy submodule with nested gitlinks"
    fi
    if [ -f "$legacy/.gitmodules" ] \
        && git -C "$legacy" config -f .gitmodules \
            --get-regexp '^submodule\..*\.path$' >/dev/null 2>&1; then
        die "refusing to relocate legacy submodule with nested submodules"
    fi
    git -C "$target" diff --quiet -- .gitmodules \
        || die "refusing to relocate with unstaged .gitmodules changes"
    LEGACY_SUBMODULE_COMMIT="$(git -C "$legacy" rev-parse HEAD)"
    LEGACY_SUBMODULE_URL="$SUBMODULE_URL"
}

relocate_legacy_submodule() {
    local target="$1" stage="$2" index temp_index
    index="$(git -C "$target" rev-parse --git-path index)"
    case "$index" in /*) ;; *) index="$target/$index" ;; esac
    temp_index="$(mktemp "${TMPDIR:-/tmp}/ai-skillz-index.XXXXXX")"
    if [ -f "$index" ]; then
        cp "$index" "$temp_index"
    else
        rm -f "$temp_index"
    fi
    mkdir -p "$target/.ai"
    if ! GIT_INDEX_FILE="$temp_index" git -C "$target" mv \
        .claude/ai.skillz "$ANCHOR_REL"; then
        rm -f "$temp_index"
        die "failed to relocate legacy submodule"
    fi
    rm -f "$temp_index"
    get_submodule_registration "$target" "$ANCHOR_REL" \
        || die "relocated submodule registration is missing"
    [ "$SUBMODULE_URL" = "$LEGACY_SUBMODULE_URL" ] \
        || die "relocated submodule URL changed unexpectedly"
    [ "$(git -C "$target/$ANCHOR_REL" rev-parse HEAD)" = "$LEGACY_SUBMODULE_COMMIT" ] \
        || die "relocated submodule commit changed unexpectedly"
    if [ "$stage" = yes ]; then
        stage_submodule_registration "$target" "$ANCHOR_REL"
        git -C "$target" update-index --force-remove .claude/ai.skillz
        git -C "$target" update-index --add --cacheinfo \
            "160000,$LEGACY_SUBMODULE_COMMIT,$ANCHOR_REL"
    fi
    ANCHOR_MODE=submodule
    ANCHOR_HEALTH=healthy
    ANCHOR_SOURCE="$target/$ANCHOR_REL"
    SOURCE_ROOT="$ANCHOR_SOURCE"
}

cmd_migrate() {
    local target_arg="" stage=no
    MIGRATE_DRY_RUN=no
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run) MIGRATE_DRY_RUN=yes; shift ;;
            --stage) stage=yes; shift ;;
            --*) die "unknown option: $1" ;;
            *) [ -z "$target_arg" ] || die "unexpected argument: $1"; target_arg="$1"; shift ;;
        esac
    done
    [ -n "$target_arg" ] || die "missing <target-repo>"
    canonical_repo "$target_arg"
    preflight_gitignore "$TARGET"
    preflight_gitmodules "$TARGET"
    preflight_anchor_parent "$TARGET"
    preflight_provider_base "$TARGET" claude
    preflight_provider_base "$TARGET" opencode
    inspect_anchor "$TARGET"
    [ "$ANCHOR_HEALTH" != broken ] && [ "$ANCHOR_HEALTH" != invalid ] \
        || die "refusing migration with $ANCHOR_HEALTH anchor"

    local inferred_root="" kind skill shape assets rest provider path asset
    local anchor_action=none planned_source="" command_provider command_name
    local command_source command_mode command_dependency
    if [ "$ANCHOR_HEALTH" = healthy ]; then
        planned_source="$ANCHOR_SOURCE"
    elif [ -L "$TARGET/.claude/ai.skillz" ] && [ -e "$TARGET/.claude/ai.skillz" ]; then
        inferred_root="$(cd "$TARGET/.claude/ai.skillz" && pwd -P)"
        planned_source="$inferred_root"
        anchor_action=local
    elif [ -f "$TARGET/.claude/ai.skillz/.git" ] \
        || legacy_anchor_registered "$TARGET"; then
        validate_legacy_submodule_move "$TARGET"
        planned_source="$TARGET/.claude/ai.skillz"
        anchor_action=submodule
    else
        while IFS='|' read -r kind skill shape assets rest; do
            [ "$kind" = skill ] && [ "$shape" != template ] || continue
            for provider in claude opencode; do
                provider_root "$provider"
                path="$TARGET/$PROVIDER_ROOT/skills/$skill"
                if [ "$shape" = generic ]; then
                    if recognized_source_root "$path" "$skill" ""; then
                        inferred_root="$RECOGNIZED_ROOT"
                        break
                    fi
                else
                    IFS=',' read -ra ASSET_LIST <<< "$assets"
                    for asset in "${ASSET_LIST[@]}"; do
                        if recognized_source_root "$path/$asset" "$skill" "$asset"; then
                            inferred_root="$RECOGNIZED_ROOT"
                            break
                        fi
                    done
                fi
                [ -z "$inferred_root" ] || break
            done
            [ -z "$inferred_root" ] || break
        done < "$MANIFEST"
        if [ -z "$inferred_root" ]; then
            while IFS='|' read -r kind command_provider command_name command_source \
                command_mode command_dependency rest; do
                [ "$kind" = command ] || continue
                provider_root "$command_provider"
                path="$TARGET/$PROVIDER_ROOT/commands/$command_name.md"
                if recognized_command_root "$path" "$command_provider" \
                    "$command_name" "$command_source"; then
                    inferred_root="$RECOGNIZED_ROOT"
                    break
                fi
            done < "$MANIFEST"
        fi
        if [ -n "$inferred_root" ]; then
            planned_source="$inferred_root"
            anchor_action=local
        fi
    fi

    if [ -n "$planned_source" ]; then
        resolve_existing_path "$planned_source" \
            || die "planned migration source is unavailable: $planned_source"
        planned_source="$RESOLVED_PATH"
    fi
    SOURCE_ROOT="$planned_source"
    MIGRATE_DIRECT=yes
    if [ "$anchor_action" = submodule ] \
        || { [ "$ANCHOR_HEALTH" = healthy ] && [ "$ANCHOR_MODE" = submodule ]; }; then
        MIGRATE_DIRECT=no
    fi
    if [ "$anchor_action" = local ]; then
        require_planned_ignore "$TARGET" anchor:symlink "$ANCHOR_REL" \
            "/$ANCHOR_REL"
    fi
    MIGRATE_PATHS=()
    MIGRATE_TARGETS=()
    MIGRATE_SOURCES=()
    MIGRATE_IGNORE_IDS=()
    MIGRATE_IGNORE_PATTERNS=()
    MIGRATE_RUNTIME=()
    MIGRATE_COPY_PATHS=()
    MIGRATE_COPY_SOURCES=()
    MIGRATE_COPY_RELS=()
    MIGRATE_COPY_IGNORE_IDS=()
    MIGRATE_COPY_RUNTIME=()
    MIGRATE_LEGACY_ROOT=""

    local changed=0 destination expected canonical_present ignore_pattern ignore_id
    while IFS='|' read -r kind skill shape assets rest; do
        [ "$kind" = skill ] && [ "$shape" != template ] || continue
        for provider in claude opencode; do
            provider_root "$provider"
            path="$TARGET/$PROVIDER_ROOT/skills/$skill"
            if [ "$shape" = generic ]; then
                [ -e "$path" ] || [ -L "$path" ] || continue
                preflight_runtime_ignores "$skill" "$TARGET"
                [ -L "$path" ] \
                    || die "migration conflict at provider destination: $path"
                ignore_id="direct:symlink:$provider:$skill"
                if [ "$MIGRATE_DIRECT" = yes ]; then
                    require_planned_ignore "$TARGET" "$ignore_id" \
                        "$PROVIDER_ROOT/skills/$skill" \
                        "/$PROVIDER_ROOT/skills/$skill"
                    require_local_path_untracked "$TARGET" \
                        "$PROVIDER_ROOT/skills/$skill"
                else
                    require_migration_path_trackable "$TARGET" \
                        "$PROVIDER_ROOT/skills/$skill" "$ignore_id"
                fi
                recognized_source_root "$path" "$skill" "" \
                    || die "unrecognized or broken migration link: $path"
                migration_root_allowed "$RECOGNIZED_ROOT" \
                    || die "migration links use mixed source roots: $RECOGNIZED_ROOT, ${MIGRATE_LEGACY_ROOT:-none}, and $planned_source"
                [ -e "$planned_source/skills/$skill" ] \
                    || die "migration target source missing: $planned_source/skills/$skill"
                if [ "$MIGRATE_DIRECT" = yes ]; then
                    LINK_TARGET="$planned_source/skills/$skill"
                    tracking_description "$TARGET" "$PROVIDER_ROOT/skills/$skill"
                else
                    relative_skill_target generic "$skill"
                    TRACKING=tracked
                fi
                if [ "$(readlink "$path")" != "$LINK_TARGET" ] \
                    || { [ "$MIGRATE_DIRECT" = yes ] && [ "$TRACKING" != ignored ]; }; then
                    MIGRATE_PATHS+=("$path")
                    MIGRATE_TARGETS+=("$LINK_TARGET")
                    MIGRATE_SOURCES+=("$planned_source/skills/$skill")
                    MIGRATE_IGNORE_IDS+=("direct:symlink:$provider:$skill")
                    if [ "$MIGRATE_DIRECT" = yes ]; then
                        MIGRATE_IGNORE_PATTERNS+=("/$PROVIDER_ROOT/skills/$skill")
                    else
                        MIGRATE_IGNORE_PATTERNS+=("")
                    fi
                    MIGRATE_RUNTIME+=("$skill")
                    changed=$((changed + 1))
                fi
            else
                [ -e "$path" ] || [ -L "$path" ] || continue
                preflight_runtime_ignores "$skill" "$TARGET"
                [ -d "$path" ] && [ ! -L "$path" ] \
                    || die "migration conflict at hybrid destination: $path"
                IFS=',' read -ra ASSET_LIST <<< "$assets"
                canonical_present=no
                for asset in "${ASSET_LIST[@]}"; do
                    if [ -e "$path/$asset" ] || [ -L "$path/$asset" ]; then
                        canonical_present=yes
                        break
                    fi
                done
                [ "$canonical_present" = yes ] || continue
                for asset in "${ASSET_LIST[@]}"; do
                    ignore_id="direct:symlink:$provider:$skill"
                    if [ "$MIGRATE_DIRECT" = yes ]; then
                        require_planned_ignore "$TARGET" "$ignore_id" \
                            "$PROVIDER_ROOT/skills/$skill/$asset" \
                            "/$PROVIDER_ROOT/skills/$skill/$asset"
                        require_local_path_untracked "$TARGET" \
                            "$PROVIDER_ROOT/skills/$skill/$asset"
                    else
                        require_migration_path_trackable "$TARGET" \
                            "$PROVIDER_ROOT/skills/$skill/$asset" "$ignore_id"
                    fi
                    [ -L "$path/$asset" ] \
                        || die "missing or unmanaged hybrid migration asset: $path/$asset"
                    recognized_source_root "$path/$asset" "$skill" "$asset" \
                        || die "unrecognized or broken hybrid migration link: $path/$asset"
                    migration_root_allowed "$RECOGNIZED_ROOT" \
                        || die "migration links use mixed source roots: $RECOGNIZED_ROOT, ${MIGRATE_LEGACY_ROOT:-none}, and $planned_source"
                    [ -e "$planned_source/skills/$skill/$asset" ] \
                        || die "migration target source missing: $planned_source/skills/$skill/$asset"
                    if [ "$MIGRATE_DIRECT" = yes ]; then
                        LINK_TARGET="$planned_source/skills/$skill/$asset"
                        tracking_description "$TARGET" \
                            "$PROVIDER_ROOT/skills/$skill/$asset"
                    else
                        relative_skill_target hybrid "$skill" "$asset"
                        TRACKING=tracked
                    fi
                    if [ "$(readlink "$path/$asset")" != "$LINK_TARGET" ] \
                        || { [ "$MIGRATE_DIRECT" = yes ] && [ "$TRACKING" != ignored ]; }; then
                        MIGRATE_PATHS+=("$path/$asset")
                        MIGRATE_TARGETS+=("$LINK_TARGET")
                        MIGRATE_SOURCES+=("$planned_source/skills/$skill/$asset")
                        MIGRATE_IGNORE_IDS+=("direct:symlink:$provider:$skill")
                        if [ "$MIGRATE_DIRECT" = yes ]; then
                            MIGRATE_IGNORE_PATTERNS+=("/$PROVIDER_ROOT/skills/$skill/$asset")
                        else
                            MIGRATE_IGNORE_PATTERNS+=("")
                        fi
                        MIGRATE_RUNTIME+=("$skill")
                        changed=$((changed + 1))
                    fi
                done
            fi
        done
    done < "$MANIFEST"

    while IFS='|' read -r kind command_provider command_name command_source command_mode \
        command_dependency rest; do
        [ "$kind" = command ] || continue
        provider_root "$command_provider"
        destination="$TARGET/$PROVIDER_ROOT/commands/$command_name.md"
        [ -e "$destination" ] || [ -L "$destination" ] || continue
        preflight_runtime_ignores "$command_name" "$TARGET"
        ignore_id="direct:symlink:$command_provider:command:$command_name"
        [ -e "$planned_source/$command_source" ] \
            || die "migration command source missing: $planned_source/$command_source"
        if [ "$MIGRATE_DIRECT" = yes ]; then
            require_planned_ignore "$TARGET" "$ignore_id" \
                "$PROVIDER_ROOT/commands/$command_name.md" \
                "/$PROVIDER_ROOT/commands/$command_name.md"
            if git_path_tracked "$TARGET" \
                "$PROVIDER_ROOT/commands/$command_name.md" \
                && [ -f "$destination" ] && [ ! -L "$destination" ] \
                && is_known_command_copy "$destination" "$planned_source" \
                    "$command_source"; then
                die "tracked canonical command copy must be untracked before local link migration: $PROVIDER_ROOT/commands/$command_name.md"
            fi
            require_local_path_untracked "$TARGET" \
                "$PROVIDER_ROOT/commands/$command_name.md"
        else
            require_migration_path_trackable "$TARGET" \
                "$PROVIDER_ROOT/commands/$command_name.md" "$ignore_id"
        fi
        if [ ! -L "$destination" ]; then
            if [ -f "$destination" ] \
                && is_known_command_copy "$destination" "$planned_source" "$command_source"; then
                if [ "$command_mode" = link ]; then
                    if [ "$MIGRATE_DIRECT" = yes ]; then
                        expected="$planned_source/$command_source"
                        ignore_pattern="/$PROVIDER_ROOT/commands/$command_name.md"
                    else
                        expected="../../$ANCHOR_REL/$command_source"
                        ignore_pattern=""
                    fi
                    MIGRATE_PATHS+=("$destination")
                    MIGRATE_TARGETS+=("$expected")
                    MIGRATE_SOURCES+=("$planned_source/$command_source")
                    MIGRATE_IGNORE_IDS+=("direct:symlink:$command_provider:command:$command_name")
                    MIGRATE_IGNORE_PATTERNS+=("$ignore_pattern")
                    MIGRATE_RUNTIME+=("$command_name")
                    changed=$((changed + 1))
                    continue
                fi
                if cmp -s "$destination" "$planned_source/$command_source"; then
                    continue
                fi
                MIGRATE_COPY_PATHS+=("$destination")
                MIGRATE_COPY_SOURCES+=("$planned_source/$command_source")
                MIGRATE_COPY_RELS+=("$command_source")
                MIGRATE_COPY_IGNORE_IDS+=("direct:symlink:$command_provider:command:$command_name")
                MIGRATE_COPY_RUNTIME+=("$command_name")
                changed=$((changed + 1))
                continue
            fi
            die "migration conflict at command destination: $destination"
        fi
        recognized_command_root "$destination" "$command_provider" \
            "$command_name" "$command_source" \
            || die "unrecognized or broken migration command link: $destination"
        migration_root_allowed "$RECOGNIZED_ROOT" \
            || die "migration links use mixed source roots: $RECOGNIZED_ROOT, ${MIGRATE_LEGACY_ROOT:-none}, and $planned_source"
        if [ "$command_mode" = link ]; then
            if [ "$MIGRATE_DIRECT" = yes ]; then
                expected="$planned_source/$command_source"
                tracking_description "$TARGET" \
                    "$PROVIDER_ROOT/commands/$command_name.md"
            else
                expected="../../$ANCHOR_REL/$command_source"
                TRACKING=tracked
            fi
            if [ "$(readlink "$destination")" = "$expected" ] \
                && { [ "$MIGRATE_DIRECT" = no ] || [ "$TRACKING" = ignored ]; }; then
                continue
            fi
            MIGRATE_PATHS+=("$destination")
            MIGRATE_TARGETS+=("$expected")
            MIGRATE_SOURCES+=("$planned_source/$command_source")
            MIGRATE_IGNORE_IDS+=("direct:symlink:$command_provider:command:$command_name")
            if [ "$MIGRATE_DIRECT" = yes ]; then
                MIGRATE_IGNORE_PATTERNS+=("/$PROVIDER_ROOT/commands/$command_name.md")
            else
                MIGRATE_IGNORE_PATTERNS+=("")
            fi
            MIGRATE_RUNTIME+=("$command_name")
        else
            MIGRATE_COPY_PATHS+=("$destination")
            MIGRATE_COPY_SOURCES+=("$planned_source/$command_source")
            MIGRATE_COPY_RELS+=("$command_source")
            MIGRATE_COPY_IGNORE_IDS+=("direct:symlink:$command_provider:command:$command_name")
            MIGRATE_COPY_RUNTIME+=("$command_name")
        fi
        changed=$((changed + 1))
    done < "$MANIFEST"

    [ -n "$planned_source" ] || {
        migration_action "make no anchor change (no recognized source anchor or direct link)"
        migration_action "make no provider link changes"
        printf 'Migration inspection complete; opencode JSON was not modified.\n'
        return 0
    }

    case "$anchor_action" in
        local)
            migration_action "create local anchor $ANCHOR_REL -> $inferred_root"
            migration_action "reconcile .gitignore block anchor:symlink"
            ;;
        submodule)
            migration_action "move legacy submodule .claude/ai.skillz -> $ANCHOR_REL"
            migration_action "preserve legacy submodule URL $LEGACY_SUBMODULE_URL"
            migration_action "preserve legacy submodule commit $LEGACY_SUBMODULE_COMMIT"
            ;;
    esac
    local i relpath
    i=0
    while [ "$i" -lt "${#MIGRATE_PATHS[@]}" ]; do
        relpath="${MIGRATE_PATHS[$i]#$TARGET/}"
        migration_action "relink $relpath -> ${MIGRATE_TARGETS[$i]}"
        migration_action "reconcile .gitignore block ${MIGRATE_IGNORE_IDS[$i]}"
        migration_action "reconcile .gitignore block runtime:${MIGRATE_RUNTIME[$i]}"
        i=$((i + 1))
    done
    i=0
    while [ "$i" -lt "${#MIGRATE_COPY_PATHS[@]}" ]; do
        relpath="${MIGRATE_COPY_PATHS[$i]#$TARGET/}"
        migration_action "refresh managed copy $relpath from selected anchor"
        migration_action "reconcile .gitignore block ${MIGRATE_COPY_IGNORE_IDS[$i]}"
        migration_action "reconcile .gitignore block runtime:${MIGRATE_COPY_RUNTIME[$i]}"
        i=$((i + 1))
    done

    if [ "$MIGRATE_DRY_RUN" = no ]; then
        IGNORE_QUIET=yes
        if [ "$anchor_action" = local ]; then
            mkdir -p "$TARGET/.ai"
            ln -s "$inferred_root" "$TARGET/$ANCHOR_REL"
            ensure_anchor_ignore "$TARGET"
            ANCHOR_MODE=symlink
            ANCHOR_HEALTH=healthy
            ANCHOR_SOURCE="$inferred_root"
            SOURCE_ROOT="$inferred_root"
        elif [ "$anchor_action" = submodule ]; then
            relocate_legacy_submodule "$TARGET" "$stage"
        fi
        MANAGED_PATHS=()
        i=0
        while [ "$i" -lt "${#MIGRATE_PATHS[@]}" ]; do
            [ -e "${MIGRATE_SOURCES[$i]}" ] \
                || MIGRATE_SOURCES[$i]="$SOURCE_ROOT/${MIGRATE_SOURCES[$i]#$planned_source/}"
            [ -e "${MIGRATE_SOURCES[$i]}" ] \
                || die "migration source disappeared: ${MIGRATE_SOURCES[$i]}"
            ln -sfn "${MIGRATE_TARGETS[$i]}" "${MIGRATE_PATHS[$i]}"
            reconcile_migration_ignore "$TARGET" "$i"
            ensure_runtime_ignores "${MIGRATE_RUNTIME[$i]}" "$TARGET"
            record_managed_path "${MIGRATE_PATHS[$i]#$TARGET/}"
            i=$((i + 1))
        done
        i=0
        while [ "$i" -lt "${#MIGRATE_COPY_PATHS[@]}" ]; do
            local copy_temp
            copy_temp="$(mktemp "$(dirname "${MIGRATE_COPY_PATHS[$i]}")/.ai-skillz-command.XXXXXX")"
            cp "$SOURCE_ROOT/${MIGRATE_COPY_RELS[$i]}" "$copy_temp"
            mv -f "$copy_temp" "${MIGRATE_COPY_PATHS[$i]}"
            set_ignore_block "$TARGET" "${MIGRATE_COPY_IGNORE_IDS[$i]}"
            ensure_runtime_ignores "${MIGRATE_COPY_RUNTIME[$i]}" "$TARGET"
            record_managed_path "${MIGRATE_COPY_PATHS[$i]#$TARGET/}"
            i=$((i + 1))
        done
        stage_paths "$TARGET" "$stage" "${MANAGED_PATHS[@]}"
        stage_ignore_changes "$TARGET" "$stage"
        IGNORE_QUIET=no
    fi
    if [ "$changed" -eq 0 ]; then
        migration_action "make no provider link changes"
    fi
    printf 'Migration inspection complete; opencode JSON was not modified.\n'
}

cmd_gitignore() {
    local target_arg="" skill=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --*) die "unknown option: $1" ;;
            *)
                if [ -z "$target_arg" ]; then target_arg="$1"
                elif [ -z "$skill" ]; then skill="$1"
                else die "unexpected argument: $1"
                fi
                shift
                ;;
        esac
    done
    [ -n "$target_arg" ] || die "missing <target-repo>"
    canonical_repo "$target_arg"
    preflight_gitignore "$TARGET"
    local provider kind name shape assets rest
    inspect_anchor "$TARGET"
    if [ "$ANCHOR_MODE" = symlink ] && [ "$ANCHOR_HEALTH" = healthy ]; then
        require_planned_ignore "$TARGET" anchor:symlink "$ANCHOR_REL" \
            "/$ANCHOR_REL"
    fi
    if [ -n "$skill" ]; then
        validate_name "$skill" skill
        if ! get_skill_record "$skill" \
            && ! get_command_record claude "$skill" \
            && ! get_command_record opencode "$skill"; then
            die "skill or command '$skill' is not in the deployment manifest"
        fi
        preflight_runtime_ignores "$skill" "$TARGET"
        ensure_runtime_ignores "$skill" "$TARGET"
    else
        while IFS='|' read -r kind name shape assets rest; do
            [ "$kind" = skill ] || continue
            preflight_runtime_ignores "$name" "$TARGET"
        done < "$MANIFEST"
        local command_provider command_source command_mode command_dependency seen='|'
        while IFS='|' read -r kind command_provider name command_source command_mode \
            command_dependency rest; do
            [ "$kind" = command ] || continue
            case "$seen" in *"|$name|"*) continue ;; esac
            seen="$seen$name|"
            preflight_runtime_ignores "$name" "$TARGET"
        done < "$MANIFEST"

        while IFS='|' read -r kind name shape assets rest; do
            [ "$kind" = skill ] || continue
            ensure_runtime_ignores "$name" "$TARGET"
        done < "$MANIFEST"
        seen='|'
        while IFS='|' read -r kind command_provider name command_source command_mode \
            command_dependency rest; do
            [ "$kind" = command ] || continue
            case "$seen" in *"|$name|"*) continue ;; esac
            seen="$seen$name|"
            ensure_runtime_ignores "$name" "$TARGET"
        done < "$MANIFEST"
    fi
    if [ "$ANCHOR_MODE" = symlink ] && [ "$ANCHOR_HEALTH" = healthy ]; then
        ensure_anchor_ignore "$TARGET"
    fi
    printf 'Updated bounded ai.skillz ignore blocks in %s/.gitignore\n' "$TARGET"
}

validate_manifest
[ $# -gt 0 ] || { usage; exit 1; }
case "$1" in
    -h|--help|help) usage ;;
    init) shift; cmd_init "$@" ;;
    update) shift; cmd_update "$@" ;;
    status) shift; cmd_status "$@" ;;
    migrate) shift; cmd_migrate "$@" ;;
    gitignore) shift; cmd_gitignore "$@" ;;
    command) shift; deploy_command "$@" ;;
    all) shift; deploy_all "$@" ;;
    *) skill="$1"; shift; deploy_skill "$skill" "$@" ;;
esac
