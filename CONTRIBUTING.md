# Contributing

## Workflow

1. Create a focused branch from the protected default branch.
2. Write a failing test before behavior changes.
3. Run `uv sync --all-groups --frozen`.
4. Run `uv run pre-commit run --all-files`.
5. Run `uv run pytest`.
6. Run `uv run pyright`.
7. Open a pull request containing test evidence, security impact, and rollback instructions.

## Prohibited Changes

- Committed credentials or private datasets.
- Autonomous LLM order authority.
- Demo or live execution without an approved design and promotion gate.
- Random allocation in any execution-capable mode.
- Claims of profitability or institutional readiness without immutable evidence.

## Legacy Code

Files under `legacy/prototype_v0/` may be used for comparison but must not be imported by the reconstructed package.
