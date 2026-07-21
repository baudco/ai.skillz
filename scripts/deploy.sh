#!/usr/bin/env bash
# Deploy ai.skillz skills + commands into a target repo via
# absolute symlinks or git-submodule-relative symlinks.
#
# Usage:
#   bash scripts/deploy.sh init <target-repo> [--url URL] [--ref REF]
#   bash scripts/deploy.sh <skill-name> <target-repo> [--method symlink|submodule]
#   bash scripts/deploy.sh all <target-repo> [--method symlink|submodule]
#   bash scripts/deploy.sh command <name|all> <target-repo> [--method ...] [--global]
#   bash scripts/deploy.sh update <target-repo> [--ref REF]
#   bash scripts/deploy.sh status <target-repo>
#   bash scripts/deploy.sh gitignore <target-repo> [skill-name]
#
# Commands (the `/name` slash-command kind) live under commands/<name>/
# and deploy as a flat `.claude/commands/<name>.md` symlink (+ any
# companion hook printed for manual settings.json merge). Use --global
# to symlink into ~/.claude/commands/ instead of a target repo.
#
# When --method is omitted the script auto-detects:
#   .claude/ai.skillz/ exists as submodule → submodule (relative links)
#   otherwise                              → symlink   (absolute links)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLZ_ROOT="$(dirname "$SCRIPT_DIR")"
DEFAULT_URL="file://${SKILLZ_ROOT}"
PATTERNS_CONF="$SKILLZ_ROOT/gitignore-patterns.conf"

# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------
die() { echo "Error: $*" >&2; exit 1; }

usage() {
    cat <<'EOF'
Usage:
  deploy.sh init   <target-repo> [--url URL] [--ref REF]
  deploy.sh <skill-name> <target-repo> [--method symlink|submodule]
  deploy.sh all    <target-repo> [--method symlink|submodule]
  deploy.sh command <name|all> <target-repo> [--method ...] [--global]
  deploy.sh update <target-repo> [--ref REF]
  deploy.sh status <target-repo>
  deploy.sh gitignore <target-repo> [skill-name]

Subcommands:
  init      Add ai.skillz as a git submodule at .claude/ai.skillz/.
  all       Deploy every skill that has a SKILL.md.
  command   Deploy a slash-command (commands/<name>/<name>.md) as a
            flat .claude/commands/<name>.md symlink. `command all`
            deploys every one. --global targets ~/.claude/commands/.
  update    Update the submodule to latest (or --ref REF).
  status    Show deployed skills and their link method.
  gitignore Update .gitignore patterns (all or single skill).

Available skills:
EOF
    ls "$SKILLZ_ROOT/skills/"
    if [ -d "$SKILLZ_ROOT/commands" ]; then
        echo ""
        echo "Available commands:"
        ls "$SKILLZ_ROOT/commands/" | grep -v '^README.md$' || true
    fi
    exit 1
}

# Detect whether the target repo has a submodule checkout.
detect_method() {
    local repo="$1"
    if [ -d "$repo/.claude/ai.skillz/.git" ] \
        || [ -f "$repo/.claude/ai.skillz/.git" ]; then
        echo "submodule"
    else
        echo "symlink"
    fi
}

# Read gitignore patterns for a skill from the centralized
# manifest and idempotently append missing entries to the
# target repo's .gitignore.
ensure_gitignore() {
    local skill="$1" target="$2"
    [ -f "$PATTERNS_CONF" ] || return 0

    # Extract patterns for [skill] section
    local in_section=false
    local patterns=()
    while IFS= read -r line; do
        # strip leading/trailing whitespace
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"

        # section header
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            if [ "${BASH_REMATCH[1]}" = "$skill" ]; then
                in_section=true
            else
                $in_section && break
            fi
            continue
        fi

        $in_section || continue
        # skip blanks and comments
        [ -z "$line" ] && continue
        [[ "$line" == \#* ]] && continue
        patterns+=("$line")
    done < "$PATTERNS_CONF"

    [ ${#patterns[@]} -eq 0 ] && return 0

    local gitignore="$target/.gitignore"
    touch "$gitignore"

    # Check if the skill header already exists
    local header="# ai.skillz/$skill"
    if grep -qFx "$header" "$gitignore" 2>/dev/null; then
        # Header present — only append truly missing patterns
        local added=0
        for pat in "${patterns[@]}"; do
            if ! grep -qFx "$pat" "$gitignore" 2>/dev/null; then
                # Insert after the header block
                echo "$pat" >> "$gitignore"
                added=$((added + 1))
            fi
        done
        [ $added -gt 0 ] \
            && echo "  .gitignore: added $added pattern(s) for $skill"
        return 0
    fi

    # Ensure a blank-line separator before our block
    if [ -s "$gitignore" ]; then
        local last_line
        last_line="$(tail -n1 "$gitignore")"
        if [ -n "$last_line" ]; then
            echo "" >> "$gitignore"
        fi
    fi

    {
        echo "$header"
        for pat in "${patterns[@]}"; do
            echo "$pat"
        done
    } >> "$gitignore"
    echo "  .gitignore: added ${#patterns[@]} pattern(s) for $skill"
}

# Add one method-specific local-link pattern without putting it in the
# cross-method manifest, where it would also hide portable relative links.
ensure_gitignore_pattern() {
    local pattern="$1" target="$2" label="$3"
    local gitignore="$target/.gitignore"

    touch "$gitignore"
    grep -qFx "$pattern" "$gitignore" 2>/dev/null && return 0

    if [ -s "$gitignore" ]; then
        local last_line
        last_line="$(tail -n1 "$gitignore")"
        [ -z "$last_line" ] || echo "" >> "$gitignore"
    fi
    echo "# ai.skillz/$label local link" >> "$gitignore"
    echo "$pattern" >> "$gitignore"
    echo "  .gitignore: added local-link pattern for $label"
}

# -------------------------------------------------------------------
# init — add ai.skillz as a git submodule
# -------------------------------------------------------------------
cmd_init() {
    local target="" url="$DEFAULT_URL" ref=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --url) url="$2"; shift 2 ;;
            --ref) ref="$2"; shift 2 ;;
            *)
                [ -z "$target" ] && { target="$1"; shift; continue; }
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    if [ -d "$target/.claude/ai.skillz" ]; then
        echo "Submodule already present at .claude/ai.skillz/"
    else
        echo "Adding ai.skillz submodule..."
        git -C "$target" submodule add "$url" .claude/ai.skillz
    fi

    if [ -n "$ref" ]; then
        echo "Checking out ref: $ref"
        git -C "$target/.claude/ai.skillz" checkout "$ref"
        git -C "$target" add .claude/ai.skillz
    fi

    mkdir -p "$target/.claude/skills"
    echo ""
    echo "Submodule ready at $target/.claude/ai.skillz/"
    echo "Deploy skills with:  deploy.sh <skill> $target"
}

# -------------------------------------------------------------------
# update — pull latest (or checkout ref) for the submodule
# -------------------------------------------------------------------
cmd_update() {
    local target="" ref=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --ref) ref="$2"; shift 2 ;;
            *)
                [ -z "$target" ] && { target="$1"; shift; continue; }
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    [ -d "$target/.claude/ai.skillz" ] \
        || die "no submodule at .claude/ai.skillz/ — run init first"

    if [ -n "$ref" ]; then
        echo "Checking out ref: $ref"
        git -C "$target/.claude/ai.skillz" checkout "$ref"
    else
        echo "Updating submodule to latest..."
        git -C "$target/.claude/ai.skillz" fetch origin
        git -C "$target/.claude/ai.skillz" pull origin HEAD
    fi
    git -C "$target" add .claude/ai.skillz
    echo "Submodule updated."
}

# -------------------------------------------------------------------
# status — show deployed skills and their link method
# -------------------------------------------------------------------
cmd_status() {
    local target="$1"
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    local skills_dir="$target/.claude/skills"
    local has_submodule="no"
    if [ -d "$target/.claude/ai.skillz/.git" ] \
        || [ -f "$target/.claude/ai.skillz/.git" ]; then
        has_submodule="yes"
    fi

    echo "Target:    $target"
    echo "Submodule: $has_submodule"
    echo ""

    if [ ! -d "$skills_dir" ]; then
        echo "No .claude/skills/ directory found."
        return
    fi

    for entry in "$skills_dir"/*/; do
        [ -d "$entry" ] || continue
        local name
        name="$(basename "$entry")"
        local status_str=""

        # strip the glob's trailing slash FIRST: `[ -L dir/ ]`
        # dereferences the symlink (always false for a dir-symlink),
        # so the tests below must see the bare path to detect it.
        entry="${entry%/}"

        if [ -L "$entry" ]; then
            local link_target
            link_target="$(readlink "$entry")"
            if [[ "$link_target" == /* ]]; then
                status_str="symlink (absolute)"
            else
                status_str="symlink (relative)"
            fi
            if [ ! -e "$entry" ]; then
                status_str="$status_str [BROKEN]"
            fi
        elif [ -L "$entry/SKILL.md" ]; then
            local link_target
            link_target="$(readlink "$entry/SKILL.md")"
            if [[ "$link_target" == /* ]]; then
                status_str="hybrid — SKILL.md symlink (absolute)"
            else
                status_str="hybrid — SKILL.md symlink (relative)"
            fi
            if [ ! -e "$entry/SKILL.md" ]; then
                status_str="$status_str [BROKEN]"
            fi
        elif [ -f "$entry/SKILL.md" ]; then
            status_str="local (template-generated)"
        else
            status_str="directory (no SKILL.md)"
        fi

        printf "  %-25s %s\n" "$name" "$status_str"
    done
}

# -------------------------------------------------------------------
# deploy — create symlinks for a single skill
# -------------------------------------------------------------------
cmd_deploy() {
    local skill_name="$1"; shift
    local target="" method=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --method) method="$2"; shift 2 ;;
            *)
                [ -z "$target" ] && { target="$1"; shift; continue; }
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    local skill_src="$SKILLZ_ROOT/skills/$skill_name"
    [ -d "$skill_src" ] || die "skill '$skill_name' not found at $skill_src"

    # Auto-detect method when not specified
    [ -z "$method" ] && method="$(detect_method "$target")"
    case "$method" in
        symlink|submodule) ;;
        *) die "invalid deployment method '$method' (expected symlink or submodule)" ;;
    esac

    local skill_dst="$target/.claude/skills/$skill_name"
    local deploy_md="$skill_src/DEPLOY.md"

    mkdir -p "$(dirname "$skill_dst")"

    echo "Deploying '$skill_name' via $method method..."

    case "$skill_name" in
        # -------------------------------------------------------
        # hybrid: SKILL.md symlink + local per-repo dirs/files
        # -------------------------------------------------------
        commit-msg)
            mkdir -p "$skill_dst/msgs"
            if [ "$method" = "submodule" ]; then
                ln -sfn "../../ai.skillz/skills/commit-msg/SKILL.md" \
                    "$skill_dst/SKILL.md"
            else
                ln -sfn "$skill_src/SKILL.md" "$skill_dst/SKILL.md"
            fi
            echo "  Linked SKILL.md, created msgs/"
            echo ""
            echo "Next steps:"
            echo "  1. Generate a style guide from commit history:"
            echo "     python $SKILLZ_ROOT/scripts/generate-style-guide.py \\"
            echo "       $target --commits 500 \\"
            echo "       --output $skill_dst/style-guide-reference.md"
            echo "  2. Optionally create conf.toml for session tracking"
            ;;

        pr-msg)
            mkdir -p "$skill_dst/msgs"
            if [ "$method" = "submodule" ]; then
                ln -sfn "../../ai.skillz/skills/pr-msg/SKILL.md" \
                    "$skill_dst/SKILL.md"
                ln -sfn "../../ai.skillz/skills/pr-msg/references" \
                    "$skill_dst/references"
                ln -sfn "../../ai.skillz/skills/pr-msg/scripts" \
                    "$skill_dst/scripts"
            else
                ln -sfn "$skill_src/SKILL.md" "$skill_dst/SKILL.md"
                ln -sfn "$skill_src/references" "$skill_dst/references"
                ln -sfn "$skill_src/scripts" "$skill_dst/scripts"
            fi
            echo "  Linked SKILL.md + references/ + scripts/, created msgs/"
            ;;

        run-tests)
            local run_tests_src="$skill_src/SKILL.md"
            if [ "$method" = "submodule" ]; then
                run_tests_src="$target/.claude/ai.skillz/skills/run-tests/SKILL.md"
            fi
            [ -f "$run_tests_src" ] \
                || die "run-tests source not found at $run_tests_src"

            local run_tests_skill="$skill_dst/SKILL.md"
            local harness_ref="$skill_dst/test-harness-reference.md"

            # Validate local state before replacing any link. Do not inspect
            # paths through a legacy whole-directory symlink.
            if [ ! -L "$skill_dst" ] && [ -d "$skill_dst" ]; then
                if [ -e "$run_tests_skill" ] \
                    && [ ! -L "$run_tests_skill" ]; then
                    die "local run-tests/SKILL.md exists; extract project-specific guidance into test-harness-reference.md before deploying"
                fi
                if [ -e "$harness_ref" ] || [ -L "$harness_ref" ]; then
                    if [ ! -f "$harness_ref" ] || [ -L "$harness_ref" ]; then
                        die "test-harness-reference.md must be a regular local file"
                    fi
                fi
            fi

            # Older deployments may link this whole directory to another
            # repository. Unlink it before creating local override state so
            # we never write through the link into that repository.
            if [ -L "$skill_dst" ]; then
                echo "  Replacing legacy whole-directory symlink"
                rm "$skill_dst"
            elif [ -e "$skill_dst" ] && [ ! -d "$skill_dst" ]; then
                die "$skill_dst exists and is not a directory"
            fi

            mkdir -p "$skill_dst"

            if [ "$method" = "submodule" ]; then
                ln -sfn "../../ai.skillz/skills/run-tests/SKILL.md" \
                    "$run_tests_skill"
            else
                ln -sfn "$skill_src/SKILL.md" "$run_tests_skill"
            fi
            echo "  Linked canonical SKILL.md"

            if [ -f "$harness_ref" ]; then
                echo "  Preserved test-harness-reference.md"
            else
                local harness_template="$SKILLZ_ROOT/templates/run-tests/SKILL.md.j2"
                if [ "$method" = "submodule" ]; then
                    harness_template="$target/.claude/ai.skillz/templates/run-tests/SKILL.md.j2"
                fi
                echo ""
                echo "Next step: bootstrap and render the local harness reference:"
                echo "  cp $harness_template \\"
                echo "    $harness_ref"
                echo "  Replace every {{ ... }} marker before using it."
            fi

            local local_link_pattern=".claude/skills/run-tests/SKILL.md"
            if [ "$method" = "symlink" ]; then
                ensure_gitignore_pattern \
                    "$local_link_pattern" "$target" "run-tests"
            elif grep -qFx "$local_link_pattern" \
                "$target/.gitignore" 2>/dev/null; then
                echo "  WARNING: remove $local_link_pattern from .gitignore"
                echo "           before tracking the relative submodule link"
            fi

            if grep -qFx ".claude/skills/run-tests" \
                "$target/.gitignore" 2>/dev/null \
                || grep -qFx ".claude/skills/run-tests/" \
                    "$target/.gitignore" 2>/dev/null; then
                echo "  WARNING: a whole-directory ignore hides the local"
                echo "           test-harness-reference.md; narrow it to"
                echo "           $local_link_pattern"
            fi
            ;;

        # -------------------------------------------------------
        # generic: whole-directory symlink
        # -------------------------------------------------------
        *)
            # Check if skill has a SKILL.md
            if [ ! -f "$skill_src/SKILL.md" ]; then
                echo "Note: $skill_name has no SKILL.md (template-only skill)."
                echo "See $deploy_md for instructions."
                return 0
            fi

            # Remove existing target so ln can create fresh
            rm -rf "$skill_dst"

            if [ "$method" = "submodule" ]; then
                ln -sfn "../ai.skillz/skills/$skill_name" "$skill_dst"
            else
                ln -sfn "$skill_src" "$skill_dst"
            fi
            echo "  Linked $skill_name/ directory"
            ;;
    esac

    # Merge gitignore patterns for this skill
    ensure_gitignore "$skill_name" "$target"

    echo ""
    echo "Deployed $skill_name → $target/.claude/skills/$skill_name"
    [ -f "$deploy_md" ] && echo "See $deploy_md for full details."
}

# -------------------------------------------------------------------
# all — deploy every skill that has a SKILL.md
# -------------------------------------------------------------------
cmd_all() {
    local target=""
    local method=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --method) method="$2"; shift 2 ;;
            *)
                [ -z "$target" ] && { target="$1"; shift; continue; }
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    local method_args=()
    [ -n "$method" ] && method_args=(--method "$method")

    local count=0
    for skill_dir in "$SKILLZ_ROOT"/skills/*/; do
        local name
        name="$(basename "$skill_dir")"
        echo "--- $name ---"
        cmd_deploy "$name" "$target" "${method_args[@]}"
        echo ""
        count=$((count + 1))
    done
    echo "Deployed $count skills to $target"
}

# -------------------------------------------------------------------
# gitignore — update .gitignore patterns standalone
# -------------------------------------------------------------------
cmd_gitignore() {
    local target="" skill=""

    while [ $# -gt 0 ]; do
        case "$1" in
            *)
                if [ -z "$target" ]; then
                    target="$1"; shift; continue
                elif [ -z "$skill" ]; then
                    skill="$1"; shift; continue
                fi
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$target" ] && die "missing <target-repo>"
    target="$(cd "$target" && pwd)"

    if [ -n "$skill" ]; then
        # Single skill
        ensure_gitignore "$skill" "$target"
    else
        # All skills that have patterns in the manifest
        local current_skill=""
        while IFS= read -r line; do
            line="${line#"${line%%[![:space:]]*}"}"
            line="${line%"${line##*[![:space:]]}"}"
            if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
                current_skill="${BASH_REMATCH[1]}"
                ensure_gitignore "$current_skill" "$target"
            fi
        done < "$PATTERNS_CONF"
    fi
    echo ""
    echo "Updated .gitignore at $target/.gitignore"
}

# -------------------------------------------------------------------
# command — symlink a slash-command's .md into .claude/commands/
# -------------------------------------------------------------------
cmd_deploy_command() {
    local name="" target="" method="" global="no"

    while [ $# -gt 0 ]; do
        case "$1" in
            --method) method="$2"; shift 2 ;;
            --global) global="yes"; shift ;;
            *)
                if [ -z "$name" ]; then name="$1"; shift; continue; fi
                if [ -z "$target" ]; then target="$1"; shift; continue; fi
                die "unexpected argument: $1"
                ;;
        esac
    done
    [ -z "$name" ] && die "missing <command-name> (or 'all')"

    # 'all' → recurse over every commands/<name>/<name>.md
    if [ "$name" = "all" ]; then
        local d n
        for d in "$SKILLZ_ROOT"/commands/*/; do
            [ -d "$d" ] || continue
            n="$(basename "$d")"
            [ -f "$d/$n.md" ] || continue
            echo "--- /$n ---"
            local fwd=("$n")
            if [ "$global" = "yes" ]; then fwd+=(--global); else fwd+=("$target"); fi
            [ -n "$method" ] && fwd+=(--method "$method")
            cmd_deploy_command "${fwd[@]}"
            echo ""
        done
        return 0
    fi

    local cmd_src_dir="$SKILLZ_ROOT/commands/$name"
    local cmd_md="$cmd_src_dir/$name.md"
    [ -f "$cmd_md" ] || die "command '$name' not found at $cmd_md"

    local cmd_dir
    if [ "$global" = "yes" ]; then
        cmd_dir="$HOME/.claude/commands"
        method="symlink"   # no submodule under ~/.claude
    else
        [ -z "$target" ] && die "missing <target-repo> (or pass --global)"
        target="$(cd "$target" && pwd)"
        cmd_dir="$target/.claude/commands"
        [ -z "$method" ] && method="$(detect_method "$target")"
    fi
    mkdir -p "$cmd_dir"
    local dst="$cmd_dir/$name.md"

    echo "Deploying command '/$name' via $method method..."
    if [ "$method" = "submodule" ]; then
        # dst is .claude/commands/<name>.md → submodule is .claude/ai.skillz/
        ln -sfn "../ai.skillz/commands/$name/$name.md" "$dst"
    else
        ln -sfn "$cmd_md" "$dst"
    fi
    echo "  Linked $name.md → $dst"

    # gitignore any per-machine state (eg. .claude/.current_session)
    [ "$global" = "yes" ] || ensure_gitignore "$name" "$target"

    # companion hook (precise-id variant) — manual settings.json merge
    local hook_json
    hook_json="$(ls "$cmd_src_dir"/*.hook.json 2>/dev/null | head -1 || true)"
    if [ -n "$hook_json" ]; then
        echo ""
        echo "Companion hook (for the precise-id variant) — merge:"
        echo "  $hook_json"
        if [ "$global" = "yes" ]; then
            echo "  into ~/.claude/settings.json (under the \"hooks\" key)"
        else
            echo "  into $target/.claude/settings.json (under \"hooks\")"
        fi
    fi

    local deploy_md="$cmd_src_dir/DEPLOY.md"
    [ -f "$deploy_md" ] && echo "See $deploy_md for full details."
}

# -------------------------------------------------------------------
# main dispatch
# -------------------------------------------------------------------
[ $# -lt 1 ] && usage

case "$1" in
    -h|--help|help) usage ;;
    init)      shift; cmd_init "$@" ;;
    update)    shift; cmd_update "$@" ;;
    status)    shift; cmd_status "$@" ;;
    gitignore) shift; cmd_gitignore "$@" ;;
    all)       shift; cmd_all "$@" ;;
    command)   shift; cmd_deploy_command "$@" ;;
    *)         cmd_deploy "$@" ;;
esac
