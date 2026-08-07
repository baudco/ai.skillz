#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(dirname "$SCRIPT_DIR")"
MANIFEST="$ROOT/deploy-manifest.conf"
DEPLOY="$ROOT/scripts/deploy.sh"
TARGET_ARG="${1:-$ROOT}"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ -f "$MANIFEST" ] || die "missing deployment manifest"
[ -d "$TARGET_ARG" ] || die "target does not exist: $TARGET_ARG"
TARGET_PHYSICAL="$(cd "$TARGET_ARG" && pwd -P)"
TARGET_TOP="$(git -C "$TARGET_PHYSICAL" rev-parse --show-toplevel 2>/dev/null)" \
    || die "target is not a git worktree"
TARGET="$(cd "$TARGET_TOP" && pwd -P)"

errors=0
skills='|'
kind=""
name=""
shape=""
assets=""
rest=""

while IFS='|' read -r kind name shape assets rest; do
    [ "$kind" = skill ] || continue
    skills="$skills$name|"
    case "$shape" in
        generic)
            [ -f "$ROOT/skills/$name/SKILL.md" ] || {
                printf 'ERROR: generic skill source missing: %s\n' "$name" >&2
                errors=$((errors + 1))
            }
            ;;
        hybrid)
            IFS=',' read -ra asset_list <<< "$assets"
            for asset in "${asset_list[@]}"; do
                [ -e "$ROOT/skills/$name/$asset" ] || {
                    printf 'ERROR: hybrid source missing: %s/%s\n' "$name" "$asset" >&2
                    errors=$((errors + 1))
                }
            done
            ;;
        template)
            [ -d "$ROOT/skills/$name" ] || {
                printf 'ERROR: template skill source missing: %s\n' "$name" >&2
                errors=$((errors + 1))
            }
            ;;
        *)
            printf 'ERROR: invalid manifest shape for %s: %s\n' "$name" "$shape" >&2
            errors=$((errors + 1))
            ;;
    esac
done < "$MANIFEST"

provider=""
source=""
mode=""
dependency=""
while IFS='|' read -r kind provider name source mode dependency rest; do
    [ "$kind" = command ] || continue
    [ -f "$ROOT/$source" ] || {
        printf 'ERROR: command source missing: %s\n' "$source" >&2
        errors=$((errors + 1))
    }
    if [ "$dependency" != - ]; then
        case "$skills" in
            *"|$dependency|"*) ;;
            *)
                printf 'ERROR: command dependency missing from manifest: %s/%s -> %s\n' \
                    "$provider" "$name" "$dependency" >&2
                errors=$((errors + 1))
                ;;
        esac
    fi
done < "$MANIFEST"

if [ "$TARGET" = "$ROOT" ]; then
    while IFS='|' read -r kind provider name source mode dependency rest; do
        [ "$kind" = command ] && [ "$provider" = opencode ] || continue
        command_path="$ROOT/.opencode/commands/$name.md"
        expected="../../$source"
        if [ ! -L "$command_path" ] \
            || [ "$(readlink "$command_path" 2>/dev/null || true)" != "$expected" ] \
            || [ ! -e "$command_path" ]; then
            printf 'ERROR: self-hosted OpenCode command link is not canonical: %s\n' \
                "$name" >&2
            errors=$((errors + 1))
        fi
    done < "$MANIFEST"
fi

index_entries="$(git -C "$TARGET" ls-files -s)"
while read -r mode blob stage path; do
    [ -n "$path" ] || continue
    if [ "$stage" = 0 ] && [ "$mode" = 120000 ]; then
        case "$path" in
            .claude/skills/*|.claude/commands/*|.opencode/skills/*|.opencode/commands/*)
                link_value="$(git -C "$TARGET" cat-file blob "$blob")"
                if [[ "$link_value" = /* ]]; then
                    printf 'ERROR: committed absolute provider link: %s\n' "$path" >&2
                    errors=$((errors + 1))
                fi
                ;;
        esac
    fi
    case "$path" in
        .claude/skills/*/msgs|.claude/skills/*/msgs/*|\
        .claude/skills/*/conf.toml|\
        .claude/git_commit_msg_LATEST.md|.claude/skills/pr-msg/pr_msg_LATEST.md|\
        .claude/review_context.md|.claude/review_regression.md|\
        .claude/wkts/*|.claude/.current_session|claude_wkts|\
        .ai/code-review/reports|.ai/code-review/reports/*|\
        .ai/taken/exports|.ai/taken/exports/*)
            printf 'ERROR: runtime state is staged or tracked: %s\n' "$path" >&2
            errors=$((errors + 1))
            ;;
    esac
done <<EOF
$index_entries
EOF

status_output="$(mktemp "${TMPDIR:-/tmp}/ai-skillz-validation.XXXXXX")"
if ! "$DEPLOY" status "$TARGET" > "$status_output" 2>&1; then
    while IFS= read -r line || [ -n "$line" ]; do
        printf '%s\n' "$line" >&2
    done < "$status_output"
    errors=$((errors + 1))
fi
rm -f "$status_output"

if [ "$errors" -gt 0 ]; then
    printf 'Deployment validation: %d error(s)\n' "$errors" >&2
    exit 1
fi
printf 'Deployment validation: 0 errors\n'
