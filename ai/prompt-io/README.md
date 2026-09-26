# AI Prompt I/O Log

This directory tracks prompt inputs and model outputs for
AI-assisted development across harnesses. New structured logs and
their unedited `.raw.md` partners live directly here. Historical
harness/service-specific directories remain in place.

## Policy

Prompt logging follows the
[NLNet generative AI policy][nlnet-ai]. Substantive contributions
record their prompts and prompting sequence, original generating
harness, known provider and exact model, UTC creation time and
timestamps, and unedited raw output. Structured logs record scope,
substantive use, raw-file linkage, and material human contributions
and edits. Records never replace earlier output or imply human
acceptance of generated changes.

[nlnet-ai]: https://nlnet.nl/foundation/policies/generativeAI/

## Usage

Entries are created by the `prompt-io` skill, which creates paired
records and may be invoked by commit workflows. `Prompt-IO:` commit
trailers name structured logs only.
Keep original generation metadata and raw output on later revision.
Human contributors remain accountable for code and workflow decisions
and corrections; generated work is not presented as human-authored.
