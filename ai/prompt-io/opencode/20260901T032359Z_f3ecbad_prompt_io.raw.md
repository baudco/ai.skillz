---
model: openai/gpt-5.6-sol
service: opencode
timestamp: 2026-09-01T03:23:59Z
git_ref: f3ecbad
diff_cmd: git diff HEAD~1..HEAD
---

The landed `commit-plan` workflow contains two avoidable sources of
latency and complexity. The `f1a0ae1` receipt state machine, together
with adjacent discovery integration, adds plan receipts, boundary IDs,
digests, transactions, invalidation, completion tracking, and
cross-repository manifests even though discovery is opt-in. Separately,
the workflow executes full project test suites while generating a plan,
then renders those same checks for execution before commit.

The correction will retain the self-locating behavior from `e581857`
while removing the later receipt integration from `commit-plan`.
Git-mgmt existing-work discovery remains independently available and
opt-in. Commit planning will perform structural staged-boundary checks
while generating messages, but project lint and test suites will run
during the rendered human execution sequence unless the user explicitly
requests pre-execution.

> `git diff HEAD~1..HEAD -- skills/commit-plan/SKILL.md`

Restore the practical self-locating workflow and define structural
planning checks separately from execution-time project suites.

> `git diff HEAD~1..HEAD -- tests/deploy/test-deploy.sh`

Remove receipt-state assertions and pin the simpler execution-time test
contract while retaining git-mgmt's opt-in discovery assertions.

The removed experimental receipt layer will be reconstructed on
`wkt/deferred_commit_plan_complexity` before its existing private-index,
parser-safe rendering, and boundary-reply commits.
