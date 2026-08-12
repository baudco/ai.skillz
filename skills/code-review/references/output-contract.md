# Code Review Output Contract

The default output is findings-first Markdown in the conversation. JSON is an
explicit export format, not an implicit side effect.

## Markdown

Start with findings. Use one block per finding:

```markdown
### [P1] Prevent duplicate payment submission

`payments/submit.py:84-91` | confidence: high | category: reliability

The retry path repeats the POST after the server may have accepted it, and no
idempotency key is supplied. A timeout can therefore create two charges.

Evidence: ...

Recommendation: ...
```

If a recommendation includes Python replacement code, use a fenced `python`
block and format it according to the target repository's deployed
`py-codestyle` skill. Keep quoted evidence byte-faithful to the reviewed diff.

Then include, in order:

1. Open questions or assumptions that affect validity.
2. Checks run, with exact commands where applicable.
3. Checks skipped, unavailable, failed, or delegated.
4. Scope: target, requested base, merge base, head, paths, and generated-file
   exclusions.
5. The final disclosure paragraph, using the active runtime values:

   ```text
   (this review was generated in some part by `<harness>` using `<model>`
   (`<provider>`))
   ```

Do not open with a general summary. Do not add a finding for praise, style
preference, or a hypothetical concern without a concrete failure path.

When no findings remain after triage, use:

```markdown
No actionable findings.

Residual risks: ...
Checks not run: ...
Scope: ...

(this review was generated in some part by `<harness>` using `<model>`
(`<provider>`))
```

Both findings and no-findings Markdown bodies contain exactly one disclosure
footer. Replace a prior footer when updating a candidate; do not duplicate it.
This footer belongs only to the complete review body, not ordinary chat
summaries, review replies, PR descriptions, commit messages, or JSON exports.

## Forge Publication

Publication is never an implicit review side effect. It is allowed only after
the complete Markdown body has been shown to the human and that exact body has
received explicit follow-up approval under the skill's human-verification
gate.

- Persist the exact candidate as an ignored `_review.md` file only after a
  follow-up message requests publication preparation. Add the disclosure
  before computing its SHA-256 digest and requesting remote-publication
  approval. The footer is part of the exact approved bytes and digest.
- Bind approval to that digest, backend, repository, PR, reviewed head, and
  non-approving `comment` event.
- Publish the approved Markdown body, not the JSON export.
- Default to one non-approving top-level review comment.
- Re-present the complete body and obtain fresh approval after any edit.
- Re-check target refs immediately before posting; never publish against a
  target which moved after review.
- Keep provider credentials, transport output, and publication commands out
  of the review body.
- Prefer `/gish review-post` as the transport. Never silently bypass an
  unavailable `gish` backend with direct forge commands.

## JSON Export

Write JSON only after an explicit export request. Use schema version `1.0`
and the adjacent `review-result-v1.schema.json` schema. The default path is:

```text
.ai/code-review/reports/<UTC-timestamp>_<short-head>.json
```

Use a reproducible fingerprint formed from path, category, symbol, and title:

1. Use the Git-reported repository-relative path with `/` separators and no
   leading `./`, normalized to Unicode NFC.
2. Use the schema category exactly.
3. Use the fully qualified symbol exactly, or `<module>` when none exists,
   normalized to Unicode NFC.
4. Normalize the title to Unicode NFC, trim its ends, collapse each run of
   whitespace to one ASCII space, and lowercase ASCII `A-Z` only.
5. Join the four UTF-8 byte strings with one NUL byte between fields, hash the
   result with SHA-256, and store the first 16 lowercase hexadecimal digits.

Conformance vector:

```text
path: src/pkg/mod.py
category: correctness
symbol: pkg.mod.parse
title: reject empty payload
fingerprint: 23acc5fc36ab85c0
```

JSON findings contain the same conclusions as Markdown. Do not add low-value
tool diagnostics merely because the schema can represent them. Commands may
be omitted when exposing them would leak credentials or sensitive paths.

SARIF, inline forge annotations, and reviewdog input remain outside this
contract. Human-verified top-level Markdown review publication uses a
separate provider adapter; JSON export remains local and is never a
publication trigger.
