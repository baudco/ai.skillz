# AI Prompt I/O Log

This directory tracks prompt inputs and model outputs for
AI-assisted development across harnesses. New structured logs and
their raw partners live directly here. Historical service-specific
directories remain in place.

## Policy

Prompt logging follows the
[NLNet generative AI policy][nlnet-ai]. Substantive contributions
record their prompts, original generating harness, known provider
and model, UTC creation time, and raw output. Structured logs record
scope, substantive use, raw-file linkage, and material human edits.

[nlnet-ai]: https://nlnet.nl/foundation/policies/generativeAI/

## Usage

Entries are created by the `prompt-io` skill and linked by
`Prompt-IO:` commit trailers. Trailers name structured logs only.
Keep original generation metadata and raw output on later revision.
Human contributors remain accountable for decisions and corrections.
