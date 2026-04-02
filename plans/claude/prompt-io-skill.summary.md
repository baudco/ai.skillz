Add `/prompt-io` skill for NLNet-compliant AI provenance

- Create `skills/prompt-io/SKILL.md` with 7-step
  protocol: detect context, classify scope, capture
  prompt, write unedited `.raw.md`, write log entry,
  ensure per-service `README.md`, emit commit trailer
- Create `skills/prompt-io/DEPLOY.md` with standard
  dual-method deploy (symlinks + submodule)
- Create `references/nlnet-policy-summary.md`
  distilling 5 NLNet policy areas for quick agent
  context
- Update `README.md` skill table with new entry
- Directory layout: `ai/prompt-io/<ai-service>/`
  with `<ts>_<hash>_prompt_io.md` + `.raw.md` pairs
- Substantive threshold table: code/config/data are
  always logged; docs/tests ask the human; chat skips
- `/commit-msg` integration deferred to separate PR

(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
