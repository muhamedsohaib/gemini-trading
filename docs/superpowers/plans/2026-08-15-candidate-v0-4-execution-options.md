# Candidate v0.4 Execution Modes

The written design and implementation plan are complete. Implementation remains `RESEARCH_ONLY` and has not started.

## Recommended: Subagent-Driven Development

Execute the implementation plan task-by-task using `superpowers:subagent-driven-development`. Each task follows RED -> verify RED -> minimal GREEN -> focused verification -> commit, with independent review checkpoints before moving to the next task. This is preferred for Candidate v0.4 because the work spans data integrity, multi-timeframe chronology, model fitting, qualification evidence, replay, and workflow governance and benefits from independent per-task review.

## Alternative: Inline Plan Execution

Execute the same implementation plan sequentially using `superpowers:executing-plans`, retaining the same TDD, verification, scope, and governance gates.

Neither mode authorizes Stage 1 ingestion, qualification dispatch, prospective-final access, paper/demo/live execution, or capital deployment during the implementation branch. Stage 1 begins only after protected merge and exact merged-main CI success.