ok i want to help me create a new prompt-io skill, very similar to
our existing plan-io one, but for rigorous prompt tracking much like
any patched code changes in `git`. the ruleset around this should be
based on the guidance provided here,

https://nlnet.nl/foundation/policies/generativeAI/

ideally we have the following feats,

- following in detail all the sensible recommendations from the
  nlnet guide linked above.

- for every substantial generated output (meaning changes or creation
  in the underlying code/data/files/content) by/from the ai model we
  track the corresponding prompts (presumably in md fmt for now)
  alongside the output summary/response from the AI in
  a ./ai/prompt-io/ subdir in the operated on code-base's repo

- any time the ai is unsure whether a prompt IO (input -> output)
  should be captured, it should prompt the human.

- human un-edited output should be tracked explicitly and separately
  prior to human edits as a priority.
