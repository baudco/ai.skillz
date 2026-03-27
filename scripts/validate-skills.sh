#!/bin/bash
# Validate all skills in ai.skillz conform to
# agentskills.io spec requirements.
#
# Usage:
#   validate-skills.sh [skills-dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${1:-$(dirname "$SCRIPT_DIR")/skills}"

errors=0
warnings=0

for skill_dir in "$SKILLS_DIR"/*/; do
    dir_name="$(basename "$skill_dir")"
    skill_md="$skill_dir/SKILL.md"

    # Skip template-only skills (no SKILL.md)
    if [ ! -f "$skill_md" ]; then
        echo "SKIP $dir_name (no SKILL.md, template-only)"
        continue
    fi

    echo "CHECK $dir_name"

    # Extract frontmatter (between first two ---)
    frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_md" \
        | head -n -1 | tail -n +2)

    # Check name field exists
    name=$(echo "$frontmatter" \
        | grep '^name:' | head -1 \
        | sed 's/^name: *//')
    if [ -z "$name" ]; then
        echo "  ERROR: missing 'name' field"
        errors=$((errors + 1))
    elif [ "$name" != "$dir_name" ]; then
        echo "  ERROR: name '$name' != dir '$dir_name'"
        errors=$((errors + 1))
    else
        echo "  OK: name matches directory"
    fi

    # Check name format (lowercase, hyphens only)
    if echo "$name" | grep -qP '[^a-z0-9-]'; then
        echo "  ERROR: name contains invalid chars"
        errors=$((errors + 1))
    fi
    if echo "$name" | grep -qP '^-|-$|--'; then
        echo "  ERROR: name has invalid hyphen usage"
        errors=$((errors + 1))
    fi

    # Check description field exists
    if ! echo "$frontmatter" | grep -q '^description:'; then
        echo "  ERROR: missing 'description' field"
        errors=$((errors + 1))
    else
        echo "  OK: description present"
    fi

    # Check line count (warn if over 500)
    lines=$(wc -l < "$skill_md")
    if [ "$lines" -gt 500 ]; then
        echo "  WARN: $lines lines (spec recommends <500)"
        warnings=$((warnings + 1))
    else
        echo "  OK: $lines lines"
    fi

    # Check for DEPLOY.md
    if [ ! -f "$skill_dir/DEPLOY.md" ]; then
        echo "  WARN: no DEPLOY.md"
        warnings=$((warnings + 1))
    fi
done

echo ""
echo "Results: $errors error(s), $warnings warning(s)"

if [ "$errors" -gt 0 ]; then
    exit 1
fi
