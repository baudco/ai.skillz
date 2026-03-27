i want you to take all the prior work surrounding all code/config/context
from the following ~/repos/,

- dotrc/doctrc/claude/skills  (most global, linked elsewhere)
- tractor/.claude/skill/ (most additional skills, mostly isolated)
- piker/.claude/skills/  (most customized to project)
- modden/.claude/skills  (most roadmapped via `skill/gish/` content)

and anything not already symlinked into any of these locations from
`~/.claude/` and factor everything **not specific to each repo** into
this new cwd. the intention is to create a new repo of generalized
skills factored out of all the other projects which can then be
linked into the most global user config `~/.claude/` (much like some
of the content is rn but linked into the `dotrc/` repo) AND into all
of those repos as needed on a per-project basis.

# (code) content extraction

ideally you acquire all the `.claude/skills/` by actually
initializing a git repo and extracting all the various commit
histories (manually or however) required from each of the repos as
needed.

for any factorable skills content try to,
- get a seemless, mostly chronological preserved git history.
- note any inter repo overlap and try to avoid bringing in commits
  which effectively result in the same patch output.
- note any content that isn't yet in git, move it into this new repo
  and incrementally allow us to commit it (likely using the
  /commit-msg skill; which should likely be the first you address).


# per-project-skill customization should drive deployable templates

note that some skills (/commit-msg, /pr-msg) will have customized
files (styule-guide-reference.md, conf.toml) under each subdir, these
should be templated out as best as possible (given analysis of all
the overrides in each repo) and for any such skill we should create
a small howto-deploy-readme and/or script which does that from the
template file(s).


# any per-skill pre-deployment work should be included

if any skill has files/content which was clearly deployed/setup but
is not documented as part of the skill's (file) content, we need to
determine how to deploy the skill fully and create a script/document
on how to do it in that skill; it is very important that we can
reproduce whatever state can be observed in the overriding repos.

# anticipating planned roadmap effects (`gish`)

any roadmaps or plans you discover which suggest further future dev of
any skill should be included in a roadmap in the per-skill content in
**this repo**.

of particular note, given most of the skills are to do with project
management using `git` and various `git` services, you should pay
special attention to `modden/xontrib/gish.xsh` and the content
in `modden/.claude/skills/gish/`.

this project is planned to be our eventual underlying util which all
the related skills will eventually use to execute various
cross-git-service actions/operations. so think not using `gh api` and
instead using `gish review request` or `gish ci run` kinda thing.

further, at least for my immediate usage we will be expecting the
highlevel human REPL UX to be built on `xonsh`, so keep that in mind
when thinking about the generalizing of various skills and how the
user will eventually expect to utilize them from a `xonsh` oriented CLI.

# plan for cross AI model service providers

per the docs which attempt to initiate a standard for (AI) "agent
skills" here,

https://agentskills.io/

adhere to a cross-provider spec per,

https://agentskills.io/specification

and though not strictly necessary, try to
organize/format/semantically orient everything to ideally work on
more then just `claude`.
