// OpenCode does not expose a blocking final-answer text hook.
// Keep the citation rule visible in each model call instead.
export const CodeNavRefsInstructions = async () => ({
  'experimental.chat.system.transform': async (_input, output) => {
    output.system.push(
      'Before your final reply, check every cited repository location. '
      + 'Use one backticked absolute path:line (or inclusive range) '
      + 'per citation, particularly for another worktree. Verify '
      + 'each file and line in the current checkout. Keep runnable '
      + 'shell blocks literal. When returning a commit plan, include '
      + 'its entire pinned native handoff, not a shortened command list. '
      + 'This instruction is not a pre-display output gate.',
    )
  },
})
