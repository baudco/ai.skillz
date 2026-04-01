Initial FOSS license evaluation for `ai.skillz`

Evaluate candidate licenses for a repo of generalized
AI agent skill definitions (markdown + scripts), with
the constraint: commercial use OK but must reciprocate.

## Constraints

- Genuine FOSS (OSI-approved preferred)
- Copyleft protection against strip-mining
- Commercial use OK *with* reciprocity
- Content is mostly markdown consumed as AI prompts,
  not compiled code

## Candidates evaluated

### AGPL-3.0 — strongest OSI-approved copyleft

- Network-use clause: if someone deploys an AI agent
  service using these skills, that's "network
  interaction" triggering copyleft — they must release
  their modifications.
- Well-understood, battle-tested.
- Downside: some corporations blanket-ban AGPL deps,
  limiting adoption. Whether markdown prompt files
  legally constitute "source code" under AGPL is
  genuinely untested territory.

### MPL-2.0 — file-level copyleft (middle ground)

- Modifications to *your* files must be shared under
  MPL, but users can freely combine with proprietary
  code alongside.
- More corporate-friendly than (A)GPL — doesn't
  "infect" the surrounding project.
- Downside: weaker protection. Someone can build a
  proprietary skill suite *around* yours and only share
  back changes to your original files.

### CC BY-SA 4.0 — copyleft for creative works

- Arguably the most natural fit since skills are
  instruction documents, not executables.
- ShareAlike = derivatives must use the same license.
  Attribution required.
- Downside: CC explicitly recommends *against* using
  their licenses for software. Would need dual-license
  (CC BY-SA for `.md` content + AGPL/MPL for scripts).

## Initial recommendation

**AGPL-3.0** as single-license choice — covers both
scripts and skill definitions as a unified work. Network
clause addresses "hosted AI agent service using our
skills for profit" scenario. Corporate adoption friction
is real but *filters for what you want*: if a company
won't contribute back, they negotiate a commercial
license (dual-license model via `baudco`).

**MPL-2.0** if maximizing adoption while keeping
reciprocity — file-level copyleft means improvements to
your skills come back but downstream projects aren't
scared off by license infection.

## Status

Superseded by expanded evaluation in
[license-evaluation.summary.md](license-evaluation.summary.md)
which adds BSL, FSL, Big Time Public License, Darklang,
Unlicense, and CC0 analysis informed by the longstanding
[tractor#103](https://github.com/goodboy/tractor/issues/103)
discussion.

(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
