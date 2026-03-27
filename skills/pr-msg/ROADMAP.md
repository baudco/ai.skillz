# `/pr-msg` Roadmap

## `gish` transport integration

Currently PR submission is manual (user runs `gh pr create`
or equivalent). When `gish` supports PR creation:

```
gish pr create <backend> --body-file pr_msg_LATEST.md
```

This enables single-command cross-service PR submission
(GitHub + Gitea + sr.ht simultaneously).

See `gish/ROADMAP.md` Phase 3 for the cross-service
sync spec.

## Post-submission tracking

The `format-reference.md` defines a metadata block
with `submitted:` fields per service. Automating this:

1. After `gish pr create`, parse the returned PR number
2. Fill the metadata block in the local pr-msg file
3. Uncomment cross-references and fill PR numbers
4. Copy to per-service subdirs for cross-linking

## Template rendering

The `format-reference.md` could be generated from the
Jinja2 template at
`templates/pr-msg/format-reference.md.j2` with
project-specific scope naming conventions.
