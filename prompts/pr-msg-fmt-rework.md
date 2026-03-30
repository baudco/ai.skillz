(/pr-msg refinement) Let's take the current state of the /pr-msg
skill and make it match the formatting of the manually edited version
i've updated here,

https://github.com/goodboy/tractor/pull/429

Also you should first,

- ensure the current state matches any (recent) updates which are not
  yet reflected in the pr's descr formatting (line len limit for eg.)

- note all the tagging given the available super set on GH (github).

- note the separation of "sections" via the `---` line markup.

---

Then we want to construct a more human readable "justification
driven flow" to all the sections as already drafted in this PR.

We want to ensure noise is reduced (such as maybe the "Scopes
changed" section which might be considered superfluous against the
actual per-file diff?) by,

- only providing prose where necessary, generally at the beginning and end of sections, and/or
  *around* bullet style segments

- bullet style should always be used where there is obvious logical
  separation of items which can be tersely prosed as hierarchical
  groupings of ideas, often this is best for piece-wise technical
  notes.

- always attempt to create a similar "TODOs before landing" section
  for any such notes seem pertinent enough that we shouldn't be
  merging the patch until complete (eg. missing tests or docs which
  can be easily added).

- try to include a "Follow up" section from any #TODO notes/comments
  which are obvious from the overall diff/history on the dev branch.

- try to always suggest and link in any related issues or past PRs
  which seem obviously related to the current patch set, possibly
  prompting the user during the /pr-msg generation process.

- prompt the user to mention any repo collaborators who's either past
  code was changed or would appear to be experienced enough to
  provide feedback on the changes requested.
