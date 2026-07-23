# Gemini Trading

Gemini Trading is a hybrid open-core research and paper-execution platform under controlled reconstruction.

## Current Status

- Promotion level: `RESEARCH_ONLY`
- Supported execution modes: `research`, `paper`
- Exchange order submission: disabled
- Profitability: not established

## Public Core

The public repository will contain canonical market-data contracts, deterministic research tools, baseline strategies, portfolio and risk primitives, paper execution, testing, security controls, and reproducible benchmark evidence.

Private strategy parameters, trained proprietary artifacts, production credentials, production infrastructure, and investor-only evidence are excluded.

## Verified Market Data Core

The repository includes a deterministic public Binance Spot market-data pipeline for research and paper only. Live mode is rejected before provider construction. The pipeline stores exact raw response evidence, validates completed candle sequences, creates deterministic canonical JSONL and dataset identities, supports provider-free replay, and independently verifies persisted evidence.

Command surface:

```text
gemini-trading market-data ingest
gemini-trading market-data replay
gemini-trading market-data verify
```

The Market Data Core establishes data integrity and reproducibility. It does not establish strategy profitability.

See:

- `docs/architecture/adr/0002-market-data-core.md` for the architecture decision and trust boundaries.
- `docs/operations/binance-market-data.md` for exact operator commands, supported intervals, storage layout, replay, verification, and the optional bounded public smoke test.
- `reports/verification/market-data-core-final.md` for final exact-head milestone evidence after Task 12 verification is complete.

## Safety

The current package fails closed when configured for demo, live, production, or an unknown mode. Historical prototype code is preserved under `legacy/prototype_v0/` and is not supported for execution.

The `main` branch requires pull requests and passing `quality` and `gitleaks` checks. Direct pushes, force pushes, and deletions are blocked by repository rules.

## Development

```bash
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run pytest
uv run pyright
```

See:

- `docs/superpowers/specs/2026-07-21-hybrid-open-core-reconstruction-design.md` for the approved architecture.
- `docs/architecture/adr/0001-paper-only-reconstruction-foundation.md` for the paper-only reconstruction decision.
- `reports/security/foundation-verification.md` for observed foundation-verification evidence and limitations.
