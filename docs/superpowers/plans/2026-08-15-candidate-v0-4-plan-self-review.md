# Candidate v0.4 Implementation Plan Self-Review

- Date: 2026-08-15
- Design spec: `docs/superpowers/specs/2026-08-15-candidate-multi-model-strategy-v0-4-design.md`
- Implementation plan: `docs/superpowers/plans/2026-08-15-candidate-multi-model-strategy-v0-4.md`
- Review boundary: `RESEARCH_ONLY`

## Result

`PASS`

The implementation plan covers the complete approved Candidate v0.4 design and is sufficiently decomposed for a single implementation cycle. No financial or execution authority is introduced.

## Coverage check

The plan explicitly covers:

- exact v0.4 identity and preservation of v0.1-v0.3 serialized/replay behavior;
- fresh canonical BTCUSDT 1h Stage 1 evidence for `[2018-01-01, 2026-08-01)`;
- deterministic UTC-aligned 1h-to-4h aggregation and strict completed-context as-of joins;
- the exact six-variable 4h numeric context and 1h tactical feature contract;
- unchanged trend and mean-reversion model families with v0.4 regime-matched fitting/calibration domains;
- the 12-hour cost-aware label and 12-hour purge/embargo chronology;
- q75/q70/q80 fold-local calibration selectivity with 160-score minimum and 800/160/160 calibration minima;
- frozen position ownership, 8h/72h/8h real-time risk durations, 1h ATR protection, and 4h regime exit semantics;
- primary/baseline/control/cost/sensitivity case inventory, including `no_4h_numeric_context`;
- opportunity-density diagnostics as evidence only, not an optimization target;
- strict development, cost, sensitivity, component-control, and 168h moving-block bootstrap gates;
- immutable qualification artifact identity, provider-free replay, and independent verification;
- manual exact-source Stage 1/qualification workflow governance under Issue #73;
- prospective seal creation only from independently verified `QUALIFIED` evidence;
- full repository quality/security checks before merge and a separate post-merge evidence sequence.

## Ambiguity and scope check

- No `TBD`, `TODO`, deferred design decision, performance-driven tuning hook, or unresolved financial parameter remains.
- Any shorthand function signature in the plan is subordinate to the exact typed contracts, input identities, validation rules, tests, and artifact semantics specified in the associated task; implementation may not widen those contracts for convenience.
- Stage 1 exact 1h candle/exclusion/segment counts are intentionally derived from the frozen closure declarations and verified hourly evidence rather than preregistered from the prior 4h dataset. This is an integrity calculation, not a performance-dependent parameter.
- Existing `LabelPolicy`/`LabelObservation` primitives already support arbitrary positive horizons and explicit entry/exit candle indices; Task 5 should reuse that generic behavior and add only the v0.4 12-hour policy construction/split protections unless RED tests prove a shared fix is required.
- Shared modules may change only through backward-compatible interfaces with explicit v0.1-v0.3 regressions. New v0.4 semantics remain version-isolated by default.
- Stage 1 and qualification dispatch are outside the implementation cycle and cannot occur before protected merge plus exact merged-main CI success.

## Implementation gate

The plan is ready for execution using the task order and RED -> GREEN -> verification -> commit discipline in the main implementation plan. This self-review does not itself authorize implementation; execution begins only after the operator chooses an execution mode.