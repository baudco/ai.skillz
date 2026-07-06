Add `\r` prior-reply picker to `claude-reply`

Roadmap #2: back-search and re-use ANY earlier reply of the session
from the compose buffer — telescope fuzzy UX over every prior turn,
for both the claude and opencode providers.

- add `M.all_replies(path)` (claude jsonl): sibling of
  `last_reply_text` that CLOSES a turn on each real user prompt
  instead of resetting — turn = consecutive assistant messages
  (tool-result carriers keep a turn open; meta/sidechain noise
  skipped); returns oldest-first `{ text, ts }` list.
- add `--list` mode to `oc-last-reply.py`: same turn-grouping from
  the sqlite store, JSON array out; fix a sqlite cursor-reuse bug
  (inner part-queries clobbered the streamed outer message rows →
  `fetchall()` the outer rows; `via_db` had the same latent bug).
- add `M.pick_reply(buf)` + buffer-local `\r` map (shadows the
  global vimrc-source map only in compose buffers) and
  `:ClaudeReplyPick`:
  - telescope custom picker when available: `ordinal` carries the
    FULL reply text so fuzzing back-searches reply content; live
    markdown preview pane; user's own sorter (fzf-native) / theme /
    mappings apply automatically; `vim.ui.select` fallback otherwise.
  - `<CR>` = "reference paging" via new `M.set_reference`: swap the
    chosen turn INTO the reference region (marker-shaped lines
    `·`-defused, folds re-bounded, buffer kept unmodified) so the
    normal `]m`/`[m` + granular `\e` workflow applies to the older
    reply; header line tagged `⟨#N/M⟩` (`⟨#M/M live⟩` on newest),
    re-`\r` to page.
  - `<C-q>` = quote the whole selected turn below the marker via the
    existing `pull_section` machinery.
- claude transcript resolution: tail-match the visible reference
  against each candidate jsonl's reconstructed last reply (mtime
  order), cache in `b:claude_reply_transcript`; opencode resolves
  per-invocation from cwd.
- verify headless: 17/17 picker checks (turn grouping across
  tool-result carriers, noise skipping, newest-first labels,
  paging + `⟨#N/M⟩` tag swap, nav/pull on a PAGED reference,
  whole-turn quoting), 2-turn fixture-db `--list` grouping, 8/8
  claude regression, real-config smoke (opencode buffer in a live
  project: `\r` map present, Telescope prompt opens fed by the real
  `--list` extraction).
- docs: README "Prior-reply picker" section, DEPLOY usage step,
  roadmap #2 marked shipped (with deltas vs draft).

Caveat documented: paging/quoting an older turn does not rewind the
conversation — composed text is still sent as the next message in
the live session.

> (this patch was generated in some part by [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
