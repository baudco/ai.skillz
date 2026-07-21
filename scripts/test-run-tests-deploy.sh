#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ai-skillz-run-tests.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

expect_failure() {
    local expected="$1"
    shift
    local output
    if output="$("$@" 2>&1)"; then
        fail "command unexpectedly succeeded: $*"
    fi
    case "$output" in
        *"$expected"*) ;;
        *) fail "missing expected error '$expected': $output" ;;
    esac
}

invalid="$TMP_ROOT/invalid-method"
mkdir -p "$invalid"
expect_failure "invalid deployment method" \
    bash "$ROOT/scripts/deploy.sh" run-tests "$invalid" --method invalid
[ ! -e "$invalid/.claude" ] \
    || fail "invalid method mutated the target"

fresh="$TMP_ROOT/fresh"
mkdir -p "$fresh"
bash "$ROOT/scripts/deploy.sh" run-tests "$fresh" --method symlink \
    >/dev/null
[ -L "$fresh/.claude/skills/run-tests/SKILL.md" ] \
    || fail "absolute SKILL.md link missing"
[ "$(readlink "$fresh/.claude/skills/run-tests/SKILL.md")" \
    = "$ROOT/skills/run-tests/SKILL.md" ] \
    || fail "absolute SKILL.md target is wrong"
grep -qFx ".claude/skills/run-tests/SKILL.md" "$fresh/.gitignore" \
    || fail "absolute SKILL.md link is not ignored"

override="$fresh/.claude/skills/run-tests/test-harness-reference.md"
printf 'consumer-owned override\n' > "$override"
before="$(sha256sum "$override")"
bash "$ROOT/scripts/deploy.sh" run-tests "$fresh" --method symlink \
    >/dev/null
after="$(sha256sum "$override")"
[ "$before" = "$after" ] || fail "redeploy changed the local override"

status="$(bash "$ROOT/scripts/deploy.sh" status "$fresh")"
case "$status" in
    *"hybrid"*"SKILL.md symlink (absolute)"*) ;;
    *) fail "absolute hybrid status not reported: $status" ;;
esac

legacy_source="$TMP_ROOT/legacy-source"
legacy_target="$TMP_ROOT/legacy-target"
mkdir -p "$legacy_source" "$legacy_target/.claude/skills"
printf 'legacy source sentinel\n' > "$legacy_source/SKILL.md"
ln -s "$legacy_source" "$legacy_target/.claude/skills/run-tests"
bash "$ROOT/scripts/deploy.sh" run-tests "$legacy_target" --method symlink \
    >/dev/null
[ ! -L "$legacy_target/.claude/skills/run-tests" ] \
    || fail "legacy directory symlink was not replaced"
[ "$(cat "$legacy_source/SKILL.md")" = "legacy source sentinel" ] \
    || fail "legacy symlink target was modified"

missing_source="$TMP_ROOT/missing-source"
mkdir -p "$missing_source/.claude/skills"
ln -s "$legacy_source" "$missing_source/.claude/skills/run-tests"
expect_failure "run-tests source not found" \
    bash "$ROOT/scripts/deploy.sh" run-tests "$missing_source" \
    --method submodule
[ -L "$missing_source/.claude/skills/run-tests" ] \
    || fail "failed submodule deploy removed the legacy link"

submodule="$TMP_ROOT/submodule"
mkdir -p "$submodule/.claude"
ln -s "$ROOT" "$submodule/.claude/ai.skillz"
bash "$ROOT/scripts/deploy.sh" run-tests "$submodule" --method submodule \
    >/dev/null
[ "$(readlink "$submodule/.claude/skills/run-tests/SKILL.md")" \
    = "../../ai.skillz/skills/run-tests/SKILL.md" ] \
    || fail "relative SKILL.md target is wrong"
[ -e "$submodule/.claude/skills/run-tests/SKILL.md" ] \
    || fail "relative SKILL.md link is broken"

local_skill="$TMP_ROOT/local-skill"
mkdir -p "$local_skill/.claude/skills/run-tests"
printf 'local skill sentinel\n' \
    > "$local_skill/.claude/skills/run-tests/SKILL.md"
expect_failure "local run-tests/SKILL.md exists" \
    bash "$ROOT/scripts/deploy.sh" run-tests "$local_skill" \
    --method symlink

bad_override="$TMP_ROOT/bad-override"
mkdir -p \
    "$bad_override/.claude/skills/run-tests/test-harness-reference.md"
expect_failure "test-harness-reference.md must be a regular local file" \
    bash "$ROOT/scripts/deploy.sh" run-tests "$bad_override" \
    --method symlink
[ ! -e "$bad_override/.claude/skills/run-tests/SKILL.md" ] \
    || fail "invalid override was mutated before rejection"

linked_override="$TMP_ROOT/linked-override"
linked_override_source="$TMP_ROOT/linked-override-source.md"
mkdir -p "$linked_override/.claude/skills/run-tests"
printf 'external override\n' > "$linked_override_source"
ln -s "$linked_override_source" \
    "$linked_override/.claude/skills/run-tests/test-harness-reference.md"
expect_failure "test-harness-reference.md must be a regular local file" \
    bash "$ROOT/scripts/deploy.sh" run-tests "$linked_override" \
    --method symlink
[ ! -e "$linked_override/.claude/skills/run-tests/SKILL.md" ] \
    || fail "linked override was mutated before rejection"

echo "run-tests deployment fixtures passed"
