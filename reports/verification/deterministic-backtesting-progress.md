# Deterministic Backtesting Progress Evidence

## Task 1 — Research foundations

Goal: establish the safe research failure taxonomy and canonical deterministic JSON/JSONL serialization used by later engine components.

Implementation branch: `feature/deterministic-backtesting-engine-v1`

Implemented:

- safe `ResearchError` hierarchy;
- finite `Decimal` formatting preserving trailing zeroes;
- strict UTC millisecond timestamp formatting;
- sorted compact UTF-8 canonical JSON;
- ordered canonical JSON Lines;
- focused unit tests for taxonomy and serialization.

Planned focused verification:

```text
uv run pytest tests/unit/research/test_errors.py tests/unit/research/test_serialization.py -q
uv run ruff format --check src/gemini_trading/research tests/unit/research
uv run ruff check src/gemini_trading/research tests/unit/research
uv run pyright src/gemini_trading/research tests/unit/research
```

Observed execution evidence will be recorded from GitHub CI before Task 1 is accepted. No exchange access, credentials, strategy logic, or order submission was introduced.

Remaining limitation: local red/green command output is not available through the GitHub connector; CI is the authoritative executable evidence for this branch.
