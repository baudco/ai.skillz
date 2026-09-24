# Fuzzy dialog selection for `ai.resume`

## User workflow

Running `ai.resume` with no name in an interactive terminal opens a
fuzzy selector over the dialogs that `ai.dlogs` would list with the
same filters. The default scope is the recorded current directory;
`-a` searches all directories and `-b` limits the harness. Selecting
a row resumes that exact dialog in its resolved launch directory.
`ai.resume NAME` keeps its current direct, non-interactive behavior.

The selector shows the dialog name first, followed by the WKT,
harness, updated time, and recorded directory as space allows. Each
choice carries the original dialog record; display text is never
parsed to recover an ID. Duplicate names remain independently
selectable. Cancelling or receiving no matches launches nothing.
Without a terminal, bare `ai.resume` reports how to supply a name or
use `ai.dlogs` instead of attempting to prompt.

## Implementation boundaries

1. Reuse `aiskillz.list_dialogs()` and the existing resume target
   resolver. Keep selection and rendering in a small optional UI
   adapter; the dialog readers and WKT layer do not import TUI code.
2. Load the UI dependency only for no-argument interactive calls.
   Preserve the startup path for `ai.resume NAME` and the Xonsh alias.
3. Compare a Python picker, starting with InquirerPy, against the
   existing `fzf` workflow. Measure cold and warm startup plus
   keystroke responsiveness with realistic dialog counts. Choose the
   default after measuring; keep any non-standard dependency optional
   unless the measured benefit justifies making it required.
4. Pass the selected record to the existing launch logic. Keep
   `--dry-run` useful after selection by printing the exact harness
   argv and working directory without starting a child process.

## Verification

- Exercise default cwd, `-a`, and `-b` filters through the same record
  selection used by `ai.dlogs`.
- Cover duplicate names across harnesses and directories, empty
  results, cancellation, non-TTY invocation, and missing UI backend.
- Verify selected harness, dialog ID, and launch directory without
  starting a real harness; retain named-resume regression coverage.
- Record benchmark commands and results before choosing a TUI backend.

This is follow-up work after the `aiskillz` rename. It does not alter
the current PR's `ai.resume NAME` behavior.
