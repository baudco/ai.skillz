# Deploying `/opencode-cleaning`

This is a generic whole-directory skill with a deterministic Python helper.
It creates no repository state and mutates OpenCode sessions only after the
skill's separate preview-token approval gate.

## Deployment

```bash
bash /path/to/ai.skillz/scripts/deploy.sh init <repo> --method symlink

bash /path/to/ai.skillz/scripts/deploy.sh opencode-cleaning <repo> \
  --provider <claude|opencode|all>
```

Use `--method submodule` after portable initialization. OpenCode skill
deployment installs its dependent command shim automatically. The explicit
command form remains available for repair:

```bash
bash /path/to/ai.skillz/scripts/deploy.sh command opencode-cleaning <repo> \
  --provider opencode
```

Quit and restart OpenCode after deployment or update. Nothing is staged unless
`--stage` is explicitly supplied.

## Prerequisites

- Python 3
- OpenCode CLI with `session list --format json`
- OpenCode CLI with `session delete <sessionID>`

The helper uses only documented CLI operations. It does not open or modify the
OpenCode SQLite database directly.
