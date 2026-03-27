#!/bin/bash
# Deploy an ai.skillz skill into a target repo.
#
# Usage:
#   deploy-skill.sh <skill-name> <target-repo-path>
#
# Example:
#   deploy-skill.sh commit-msg ~/repos/myproject
#   deploy-skill.sh py-codestyle ~/repos/myproject

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLZ_ROOT="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <skill-name> <target-repo-path>"
    echo ""
    echo "Available skills:"
    ls "$SKILLZ_ROOT/skills/"
    exit 1
fi

SKILL_NAME="$1"
TARGET_REPO="$2"
SKILL_SRC="$SKILLZ_ROOT/skills/$SKILL_NAME"
SKILL_DST="$TARGET_REPO/.claude/skills/$SKILL_NAME"

if [ ! -d "$SKILL_SRC" ]; then
    echo "Error: skill '$SKILL_NAME' not found at $SKILL_SRC"
    exit 1
fi

if [ ! -d "$TARGET_REPO" ]; then
    echo "Error: target repo '$TARGET_REPO' not found"
    exit 1
fi

# Check if DEPLOY.md exists for instructions
DEPLOY_MD="$SKILL_SRC/DEPLOY.md"
if [ ! -f "$DEPLOY_MD" ]; then
    echo "Warning: no DEPLOY.md found for $SKILL_NAME"
fi

# Check if skill has a SKILL.md (run-tests is template-only)
if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
    echo "Note: $SKILL_NAME has no SKILL.md (template-only skill)."
    echo "See $DEPLOY_MD for instructions."
    exit 0
fi

mkdir -p "$SKILL_DST"

# Skills that need per-repo customization get
# selective symlinks; fully generic skills get a
# directory symlink.
case "$SKILL_NAME" in
    commit-msg)
        ln -sfn "$SKILL_SRC/SKILL.md" "$SKILL_DST/SKILL.md"
        mkdir -p "$SKILL_DST/msgs"
        echo "Symlinked SKILL.md, created msgs/"
        echo ""
        echo "Next steps:"
        echo "  1. Generate a style guide:"
        echo "     Have claude analyze your commit history"
        echo "     and write .claude/skills/commit-msg/style-guide-reference.md"
        echo "  2. Optionally create conf.toml for session tracking"
        ;;
    pr-msg)
        ln -sfn "$SKILL_SRC/SKILL.md" "$SKILL_DST/SKILL.md"
        ln -sfn "$SKILL_SRC/references" "$SKILL_DST/references"
        mkdir -p "$SKILL_DST/msgs"
        echo "Symlinked SKILL.md + references/, created msgs/"
        ;;
    *)
        # Fully generic skill: symlink the whole directory
        rm -rf "$SKILL_DST"
        ln -sfn "$SKILL_SRC" "$SKILL_DST"
        echo "Symlinked $SKILL_NAME/ directory"
        ;;
esac

echo ""
echo "Deployed $SKILL_NAME to $TARGET_REPO"
echo "See $DEPLOY_MD for full details."
