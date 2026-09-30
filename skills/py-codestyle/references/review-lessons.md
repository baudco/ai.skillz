# Review lessons: runtime and fault tests

Apply these principles to new Python code and materially revised
tests. An optional repository-owned reference at
`<repo-root>/.ai/py-codestyle/review-lessons.md` may add the
project's topology and examples. Resolve it from the active
worktree. The owning skills define Git, review, and test
authorization.

## Explain the operation before its machinery

- Describe what a type lets the caller do and why it exists. Put
  that purpose in the class docstring, not a detached comment above
  the class. Give methods their own contracts when behavior is not
  obvious from the signature.
- Name concrete types, fields, methods, and namespace paths. Avoid
  phrases like "the old receiver", "drive into the wrapper", or
  "the control path" without identifying the actual objects.
- Explain the subject and action accurately: a task calls a method
  or waits on an event; a packet is read, decoded, or published.
  Replacing a field does not retroactively change a call already
  waiting in the object previously stored there.
- Name test wrappers by the behavior they simulate. Describe the
  operation directly rather than inventing ambiguous labels.
- Name the owner and purpose of each connection when multiple
  channels or controllers participate in a test.

## Render code references as code

- Use reStructuredText inline literals, e.g. ``Context.cancel()``,
  in Python docstrings intended for that documentation pipeline.
  In Markdown documents use inline code, e.g. `Context.cancel()`.
  Follow the surrounding comment convention, but quote code/type
  names rather than treating them as ordinary prose.
- Qualify field references with their declaring type on first use.
  Name the concrete instance expression where that distinction
  matters. Re-qualify after another object could become the referent.
- Retain useful explanations of call paths during refactoring.
  Correct obsolete claims narrowly; do not delete the entire note
  because the surrounding implementation changed.
- Use editor-jumpable source locations in replies according to
  `code-nav-refs`. Verify the active reply worktree root, and use
  absolute paths for files outside it.

## Make types and cases visible at their declarations

- Type helper parameters and returns when their contract is not
  obvious. Lay out nontrivial signatures, compound expressions,
  and case collections across lines. Annotate non-obvious locals,
  tuple-unpacked values, and context-manager bindings using
  `py-codestyle` rules.
- Explain parameter meanings beside the signature or in the
  docstring. Do not make readers inspect every called function to
  learn what ``mode``, ``marker``, or a shared result dict means.
- Name parametrized cases by the fault or healthy baseline and
  the behavior each case proves.
- Group a larger case matrix under a clear heading and bullets.
  Explain which connections remain usable for each group and what
  property it proves. A terse label plus an ambiguous comment is
  not a substitute for this case description.
- Define helpers before callers when that improves local reading.
  Unpack context-manager results at the ``as`` binding when the
  surrounding code does so; avoid retaining an unnamed pair only
  to unpack it in the next statement.

## Document the proof, not merely the test's sequence

Every materially rewritten regression should make these clear:

- The original failure mechanism and intended invariant.
- The exact tasks, fields, channels, events, and relevant order.
- The signal proving the fault is actually active. Installing a
  wrapper is not proof that a send or receive has reached its wait.
- Why each assertion is needed, particularly event-dispatch and
  final-outcome branches. Explain what fails the test, not merely
  that "it fails".
- What the test does not prove. A cancellable event wait models
  stalled task progress; it does not prove behavior under an
  uninterruptible syscall or a specific network fault.

When a test swaps an I/O object, distinguish calls already pending
on the old object from calls that later select its replacement.
Prove the replacement reached its simulated fault before asserting
shutdown behavior.

For cancellation and reaping, distinguish cooperative cancellation
through an unaffected channel from escalation when the needed
channel is unavailable. Assert process exit and reaping before
watchdog rescue can conceal failure. Forced cleanup cannot make a
failed runtime shutdown pass.

Do not replace removed assertions with an unverified claim that a
new suite covers them. Map the prior checks to new checks; resource
closure, error cause, cancellation provenance, final results,
process exit, and reaping are distinct facts.

## Keep the test controller separate for a reason

- A subject intended to receive OS SIGINT belongs in a separate
  process when signalling it inside ``pytest`` would interrupt the
  runner itself. Document that rationale at the entry point and
  test, not only in a review response.
- A runnable demonstration belongs under the repository's examples
  convention when it can be invoked from the console and pytest.
  Keep the harness-specific controller and assertions in tests.
- Extract subprocess lifetime, output decoding, deadlines, and
  failure cleanup into a small context manager or monitor when
  that makes the scenario assertions readable. Do not grow a
  general process framework before another caller needs it.
- Explain why an external observer is necessary. A connection
  inside the process under test cannot independently observe that
  process's OS exit or guarantee a watchdog deadline if it hangs.
- Use ``TimeoutError`` for an external watchdog deadline, rather
  than disguising it as an arbitrary assertion failure.
- Reuse existing address/process helpers after checking their
  actual guarantees. A random address is not an atomic port
  reservation; retain collision rejection at runtime startup.
- Reaping assertions must not quietly invoke a global cleanup
  tool. Restrict failure rescue to retained test-owned identities.

## Separate state ownership, compatibility, and policy

- Moving private fields into a status type should give them one
  authoritative owner. Audit actual internal and downstream uses
  before preserving every old private name or constructor keyword.
- Do not add tests that require a compatibility layer solely
  because the agent introduced that layer. Existing consumer
  requirements, not newly invented tests, justify compatibility.
- Prefer existing public accessors for downstream callers.
  A getter-only property returning mutable state does not make
  that state read-only, and a public wrapper does not make private
  fields a public interface.
- Put a pure state predicate on the state owner. Share the common
  predicate while retaining intentionally different caller guards.
  Receipt of a final outcome and decoding its result may require
  separate checks, including for falsey results.
- A locally observed transport loss does not establish that a
  peer requested cancellation or that its application task failed.
  Keep fault observation, cancellation provenance, and notification
  policy distinct. Do not invent a canceller to make a test pass.
- Log short-circuit cases without claiming an operation was
  scheduled. Assert meaningful return values: first scheduling,
  duplicate requests, completed teardown, and finalizers can have
  different outcomes.

## Adopt human edits and make review boundaries trustworthy

- Read both the staged snapshot and the human's unstaged changes
  before remediation. Use their comment/doc edits as examples of
  the desired explanation, preserving useful rationale and TODOs.
- Proposed future reuse belongs in a focused TODO naming the
  concrete adjacent machinery; it is not permission for an
  immediate broad refactor.
- Staged is not the same as reviewed. Do not include an unreviewed
  helper in a commit merely because the agent previously told the
  human to stage it. Make the actual file boundary explicit.
- Keep larger engineering handoffs independently reviewable when
  requested. Test implementation and future infrastructure design
  need not be committed together.
- Match local review replies to original saved IDs/anchors even
  after a file move. Preserve human comments and review markers;
  avoid duplicate replies to already-answered feedback.
- Attribute failures by comparing the exact changed boundary
  with its parent; broad checks can expose earlier regressions.
