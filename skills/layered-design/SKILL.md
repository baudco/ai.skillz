---
name: layered-design
description: >
  Design module and API boundaries for a substantial software change.
  Use for architecture, layering, or design review before implementation;
  skip small local edits that need no design pass.
compatibility: >
  Works with agentic coding harnesses that can inspect a repository.
metadata:
  author: goodboy
  version: "0.1"
argument-hint: "[subsystem or change]"
---

# Layered design

Design a substantial change from the outside in. This skill produces
an understandable design, not the implementation. If implementation
is also authorized, use the design to guide that later work without
adding a separate approval step for routine decisions.

## Start with the operation

- Describe what a user or caller does, what it supplies, and what it
  receives. Include one realistic input/output example when a public
  API or CLI is involved.
- Trace that operation through existing entry points and data. Name
  the concrete records and paths involved. Separate observed behavior
  from proposed behavior.
- Define unfamiliar terms where they first appear. Prefer the domain's
  nouns over generic labels such as "store", "candidate", or "target"
  when those labels hide what the code actually represents.

## Choose the boundaries

- State which modules own discovery, decisions, persistence, and
  presentation when those responsibilities differ. Show dependency
  direction and where the public API sits.
- Place low-level provider or tool interactions behind a clear
  boundary when that makes their replacement possible. Avoid adding
  layers solely to match a template.
- Specify the main success path and meaningful failure or ambiguity
  cases. Add compatibility or migration machinery only for an
  evidenced requirement.
- If a diagram clarifies the flow, prefer D2 syntax when practical.
  Label arrows with actions or data so their direction is clear.

## Hand off a reviewable design

- Identify the public functions and modules that will need docstrings
  explaining their role in the operation and adjacent machinery.
- Keep examples consistent with the proposed API and terms.
  Show a concrete record or command where prose would be ambiguous.
- Re-read the design as someone who has not seen the discussion: the
  entry point, data flow, ownership, and reason for each boundary
  should be clear before helper code exists.

Scale this to the change. A small repair needs no architecture essay;
for a larger subsystem, a short design sketch can guide the edits.
