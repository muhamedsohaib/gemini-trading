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
