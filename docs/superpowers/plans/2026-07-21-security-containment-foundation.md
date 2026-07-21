# Security Containment and Engineering Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the compromised prototype repository into a secret-free, quarantined, paper-only Python project with deterministic safety guards, automated validation, and enforceable repository governance.

**Architecture:** The existing prototype is preserved as a non-importable historical baseline under `legacy/prototype_v0/`. A new installable package under `src/gemini_trading/` owns all future executable behavior. Runtime policy permits only `research` and `paper`; unsafe modes fail closed before any exchange adapter can be constructed. CI validates formatting, linting, typing, tests, package builds, secrets, dependencies, and repository policy.

**Tech Stack:** Python 3.12, uv, hatchling, pytest, Hypothesis, Ruff, Pyright, detect-secrets, pip-audit, GitHub Actions.

## Global Constraints

- All execution remains paper-only until explicit promotion gates are satisfied.
- Failure defaults to no trade.
- Risk governance remains independent of strategy and model code.
- Completed-candle strategies may never consume incomplete candles.
- No production exploration or random allocation is permitted.
- Secrets must never be committed; the exposed Supabase credential must be rotated before history cleanup.
- OpenAI models may not submit orders, override risk decisions, raise limits, deploy models, or change production configuration autonomously.
- The public repository contains no production credentials, private datasets, proprietary model artifacts, or investor-only evidence.
- The current prototype remains historical evidence and is not imported by the reconstructed package.
- Every task ends with a focused commit and an independently verifiable result.

---

## Planned File Map

### Files removed from the executable root

- `.env.local`
- `fetch_market.py`
- `rl_optimizer.py`
- `strategy_selector.py`
- `test_ledger.py`
- `xgboost_engine.py`
- `chronos_engine.py.txt`
- `kronos_engine.py.txt`

The Python prototype files are moved, after secret removal, to `legacy/prototype_v0/`. `.env.local` and the database-writing `test_ledger.py` are deleted rather than archived.

### New project foundation

- `.env.example` — safe configuration names with non-secret values.
- `.github/CODEOWNERS` — ownership for sensitive paths.
- `.github/dependabot.yml` — dependency update policy.
- `.github/pull_request_template.md` — security, test, and rollback checklist.
- `.github/workflows/ci.yml` — quality, test, build, and security gates.
- `.pre-commit-config.yaml` — local validation hooks.
- `.python-version` — Python 3.12.
- `.secrets.baseline` — detect-secrets baseline generated after cleanup.
- `CONTRIBUTING.md` — branch and validation workflow.
- `SECURITY.md` — responsible disclosure and secret-response policy.
- `pyproject.toml` — package and tool configuration.
- `uv.lock` — exact dependency lock.
- `legacy/prototype_v0/README.md` — historical-only warning and defect inventory.
- `src/gemini_trading/__init__.py` — package version.
- `src/gemini_trading/safety/execution_mode.py` — fail-closed runtime mode policy.
- `src/gemini_trading/safety/regression_guards.py` — pure safety invariants covering Version 0 defects.
- `src/gemini_trading/safety/repository_policy.py` — tracked-file policy validation.
- `tests/unit/safety/test_execution_mode.py` — runtime policy tests.
- `tests/regression/test_version0_guards.py` — known-defect regression tests.
- `tests/unit/safety/test_repository_policy.py` — repository policy tests.
- `tests/acceptance/test_paper_only_package.py` — package-level paper-only acceptance test.
- `docs/architecture/adr/0001-paper-only-reconstruction-foundation.md` — governing decision.
- `docs/operations/credential-rotation-runbook.md` — repeatable rotation procedure.
- `docs/operations/security-incident-2026-07-21.md` — sanitized incident record.
- `reports/security/foundation-verification.md` — final evidence report.

---

### Task 1: Rotate the Exposed Supabase Credential and Capture Incident Evidence

**Files:**
- Create: `docs/operations/security-incident-2026-07-21.md`
- Create: `docs/operations/credential-rotation-runbook.md`

**Interfaces:**
- Consumes: Supabase project dashboard audit logs and credential controls.
- Produces: a confirmed invalid old key, a new private credential stored outside Git, and a sanitized incident record.

- [ ] **Step 1: Disable and replace the exposed service-role credential**

In Supabase, rotate the service-role signing secret or service-role key using the project credential controls. Store the replacement only in the private deployment secret store. Do not paste either the old or replacement value into chat, terminal history, issue comments, commits, screenshots, or documentation.

Expected result: requests authenticated with the old credential fail, while the replacement credential is available only through the chosen private secret store.

- [ ] **Step 2: Inspect access logs and record the bounded review window**

Review Supabase authentication, database, API, and project logs from the first public commit timestamp through the rotation timestamp. Record only UTC times, affected tables, suspicious source indicators, and actions taken. Do not record tokens, full IP addresses in the public repository, row contents, or personal data.

- [ ] **Step 3: Write the sanitized incident record**

Create `docs/operations/security-incident-2026-07-21.md` with this exact structure:

```markdown
# Supabase Service-Role Credential Exposure — 2026-07-21

## Classification

- Severity: Critical
- Status: Contained
- Affected system: Gemini Trading prototype Supabase project
- Secret type: Service-role credential

## Exposure

The prototype repository committed a Supabase service-role credential in tracked files and Git history. Service-role credentials are prohibited in public source code.

## Containment Performed

- The exposed credential was revoked or rotated before repository history cleanup.
- The replacement credential is stored outside Git in a private secret-management location.
- Public source files no longer contain an active credential.
- Repository history is scheduled for sanitization under the approved reconstruction plan.

## Log Review

The review covered the interval from the first public secret-bearing commit through credential rotation. Detailed source identifiers, database contents, and private operational evidence are retained outside the public repository.

## Public Findings

Record one of the following conclusions after reviewing the logs:

- No confirmed unauthorized use was identified in the reviewed evidence.
- Unauthorized or unexplained activity was identified and escalated through the private incident process.

## Corrective Controls

- Secret scanning in local pre-commit hooks and CI.
- Least-privilege credentials per environment.
- No service-role credentials in application code.
- Mandatory rotation before history sanitization.
- Pull-request-only changes to protected branches.

## Closure Criteria

- The old credential is confirmed invalid.
- Git history contains no active secret.
- CI rejects future secret-bearing commits.
- The private incident evidence package is retained securely.
```

Replace the two-choice `Public Findings` subsection with the single conclusion supported by the reviewed evidence before committing.

- [ ] **Step 4: Write the credential rotation runbook**

Create `docs/operations/credential-rotation-runbook.md` with this exact content:

```markdown
# Credential Rotation Runbook

## Trigger Conditions

Rotate a credential immediately when it is committed, pasted into an issue or chat, exposed in logs, shared with an unauthorized party, or suspected of misuse.

## Required Order

1. Disable, revoke, or rotate the exposed credential.
2. Confirm that the old value no longer authenticates.
3. Issue a least-privilege replacement.
4. Update the private secret store.
5. Restart or redeploy only the services that require the replacement.
6. Review access logs for the exposure interval.
7. Remove the value from current files.
8. Rewrite Git history when necessary.
9. Force-push sanitized refs only after team coordination.
10. Run local and CI secret scans against the full history.

## Prohibited Actions

- Do not delay rotation until after Git cleanup.
- Do not paste a replacement credential into source code.
- Do not store service-role credentials in frontend or ordinary local application configuration.
- Do not publish raw incident evidence containing personal data, tokens, complete IP addresses, or database records.

## Verification

Rotation is complete only when the old value fails authentication, all intended services operate with the replacement, repository scans pass, and the incident record is updated.
```

- [ ] **Step 5: Commit the incident documentation**

```bash
git add docs/operations/security-incident-2026-07-21.md docs/operations/credential-rotation-runbook.md
git commit -m "docs(security): record credential containment"
```

Expected result: one documentation-only commit containing no credential values.

---

### Task 2: Sanitize Current Files and Rewrite Git History

**Files:**
- Delete: `.env.local`
- Delete: `test_ledger.py`
- Modify: `.gitignore`
- Create: `.env.example`
- Move: `fetch_market.py` → `legacy/prototype_v0/fetch_market.py`
- Move: `rl_optimizer.py` → `legacy/prototype_v0/rl_optimizer.py`
- Move: `strategy_selector.py` → `legacy/prototype_v0/strategy_selector.py`
- Move: `xgboost_engine.py` → `legacy/prototype_v0/xgboost_engine.py`
- Move: `chronos_engine.py.txt` → `legacy/prototype_v0/chronos_engine.py.txt`
- Move: `kronos_engine.py.txt` → `legacy/prototype_v0/kronos_engine.py.txt`
- Create: `legacy/prototype_v0/README.md`

**Interfaces:**
- Consumes: rotated credential state from Task 1.
- Produces: a current tree with no secret-bearing files and a non-executable historical prototype directory.

- [ ] **Step 1: Replace `.gitignore` with the complete policy**

```gitignore
# Python environments and caches
.venv/
venv/
ENV/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.pyright/
.ruff_cache/
.coverage
htmlcov/

# Builds and packages
build/
dist/
*.egg-info/

# Secrets and local configuration
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
config.json
secrets/

# Runtime state and local databases
*.log
*.sqlite
*.sqlite3
q_table.json

# Editors and operating systems
.vscode/
.idea/
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Create the safe configuration example**

Create `.env.example`:

```dotenv
GEMINI_TRADING_MODE=paper
SUPABASE_URL=https://example-project.supabase.co
SUPABASE_ANON_KEY=replace-with-a-low-privilege-development-key
```

The example deliberately excludes `SUPABASE_SERVICE_ROLE_KEY`.

- [ ] **Step 3: Quarantine the sanitized prototype**

Move the six prototype source files into `legacy/prototype_v0/`. Before moving `fetch_market.py`, remove unused imports and ensure it contains no secret values. Delete `.env.local` and `test_ledger.py`; do not archive either file.

Create `legacy/prototype_v0/README.md`:

```markdown
# Gemini Trading Prototype Version 0

This directory preserves the original prototype logic for historical comparison and regression analysis.

## Restrictions

- It is not an installable package.
- It is excluded from production and paper execution paths.
- It must not contain credentials.
- It must not be imported by `src/gemini_trading`.
- It may contain known logic defects documented by the reconstruction audit.

## Known Defects

- Downtrend text is truncated and can route into uptrend logic.
- Candle completion is not enforced consistently.
- Future-label trailing rows can receive false ranging labels.
- Allocation exploration is random and is not functioning reinforcement learning.
- Position state, duplicate-decision prevention, true risk sizing, and executable exits are absent.
- Chronos and Kronos placeholders are empty.

The reconstructed package must prove improvements through automated regression tests rather than deleting unfavorable history.
```

- [ ] **Step 4: Rewrite repository history after current-tree cleanup**

Run from a fresh local clone with `git-filter-repo` installed:

```bash
git filter-repo --force \
  --path .env.local \
  --path .env.local.txt \
  --path test_ledger.py \
  --invert-paths
```

Then run a replacement pass using a private file containing the exact exposed credential followed by `==>REMOVED_SUPABASE_SERVICE_ROLE_KEY`:

```bash
git filter-repo --force --replace-text ../private-secret-replacements.txt
```

Delete `../private-secret-replacements.txt` securely after the rewrite. Do not commit or upload it.

Force-push only the approved reconstruction branch first:

```bash
git push --force-with-lease origin design/hybrid-open-core-reconstruction
```

After verification and coordination, sanitize `main` and any other affected refs using the same rewritten commit graph.

- [ ] **Step 5: Verify current tree and full history, then commit**

```bash
git grep -n -I -E 'SUPABASE_SERVICE_ROLE_KEY|service_role|eyJ[a-zA-Z0-9_-]+\.' -- . ':!docs/operations/security-incident-2026-07-21.md'
git log -p --all | grep -E 'SUPABASE_SERVICE_ROLE_KEY|service_role|eyJ[a-zA-Z0-9_-]+\.'
git status --short
```

Expected result: the searches return no credential value; `git status --short` contains only the intended sanitized moves, deletions, and policy files.

```bash
git add -A
git commit -m "security: quarantine prototype and remove secret material"
```

---

### Task 3: Create the Installable Python Foundation

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `src/gemini_trading/__init__.py`
- Create: `src/gemini_trading/safety/__init__.py`
- Create: `tests/unit/test_package.py`

**Interfaces:**
- Consumes: sanitized repository tree from Task 2.
- Produces: installable package `gemini-trading` and standard commands used by all later tasks.

- [ ] **Step 1: Write the failing package test**

Create `tests/unit/test_package.py`:

```python
from gemini_trading import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Create `.python-version` and `pyproject.toml`**

Create `.python-version`:

```text
3.12
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "gemini-trading"
version = "0.1.0"
description = "Hybrid open-core trading research and paper-execution platform"
readme = "README.md"
requires-python = ">=3.12,<3.13"
license = { text = "Apache-2.0" }
authors = [{ name = "Gemini Trading Contributors" }]
dependencies = []

[dependency-groups]
dev = [
  "build>=1.2",
  "detect-secrets>=1.5",
  "hypothesis>=6.130",
  "pip-audit>=2.8",
  "pre-commit>=4.2",
  "pyright>=1.1.400",
  "pytest>=8.3",
  "pytest-cov>=6.1",
  "ruff>=0.12",
]

[tool.hatch.build.targets.wheel]
packages = ["src/gemini_trading"]

[tool.pytest.ini_options]
addopts = "-ra --strict-config --strict-markers --cov=gemini_trading --cov-report=term-missing"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.12"
typeCheckingMode = "strict"
reportMissingTypeStubs = "warning"
```

- [ ] **Step 3: Run the test to confirm the package is missing**

```bash
uv lock
uv sync --all-groups
uv run pytest tests/unit/test_package.py -v
```

Expected result: FAIL during import because `gemini_trading` does not exist.

- [ ] **Step 4: Add the minimal package implementation and rerun validation**

Create `src/gemini_trading/__init__.py`:

```python
"""Gemini Trading public open-core package."""

__version__ = "0.1.0"
```

Create `src/gemini_trading/safety/__init__.py`:

```python
"""Fail-closed runtime and repository safety controls."""
```

Run:

```bash
uv run pytest tests/unit/test_package.py -v
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m build
```

Expected result: all commands pass and `dist/` contains a source distribution and wheel.

- [ ] **Step 5: Commit**

```bash
git add .python-version pyproject.toml uv.lock src tests/unit/test_package.py
git commit -m "build: establish typed Python package foundation"
```

---

### Task 4: Implement the Fail-Closed Paper-Only Runtime Policy

**Files:**
- Create: `src/gemini_trading/safety/execution_mode.py`
- Create: `tests/unit/safety/test_execution_mode.py`
- Create: `tests/acceptance/test_paper_only_package.py`

**Interfaces:**
- Consumes: environment variable `GEMINI_TRADING_MODE`.
- Produces: `ExecutionMode`, `RuntimePolicy`, `UnsafeExecutionModeError`, and `load_runtime_policy()`.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/safety/test_execution_mode.py`:

```python
import pytest

from gemini_trading.safety.execution_mode import (
    ExecutionMode,
    UnsafeExecutionModeError,
    load_runtime_policy,
)


def test_default_mode_is_paper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_TRADING_MODE", raising=False)

    policy = load_runtime_policy()

    assert policy.mode is ExecutionMode.PAPER
    assert policy.exchange_submission_allowed is False


@pytest.mark.parametrize("value", ["research", "paper", "RESEARCH", " PAPER "])
def test_safe_modes_are_accepted(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", value)

    policy = load_runtime_policy()

    assert policy.exchange_submission_allowed is False


@pytest.mark.parametrize("value", ["demo", "live", "production", "", "random"])
def test_unsafe_or_unknown_modes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", value)

    with pytest.raises(UnsafeExecutionModeError):
        load_runtime_policy()
```

- [ ] **Step 2: Run the tests and verify failure**

```bash
uv run pytest tests/unit/safety/test_execution_mode.py -v
```

Expected result: FAIL because `execution_mode.py` is absent.

- [ ] **Step 3: Implement the runtime policy**

Create `src/gemini_trading/safety/execution_mode.py`:

```python
"""Runtime mode policy that refuses all exchange submission."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class ExecutionMode(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"


class UnsafeExecutionModeError(RuntimeError):
    """Raised when configuration requests a prohibited execution mode."""


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    mode: ExecutionMode
    exchange_submission_allowed: bool = False


def load_runtime_policy(environment: dict[str, str] | None = None) -> RuntimePolicy:
    source = os.environ if environment is None else environment
    raw_mode = source.get("GEMINI_TRADING_MODE", ExecutionMode.PAPER.value)
    normalized = raw_mode.strip().lower()

    try:
        mode = ExecutionMode(normalized)
    except ValueError as exc:
        raise UnsafeExecutionModeError(
            f"Execution mode {raw_mode!r} is prohibited; only research and paper are allowed."
        ) from exc

    return RuntimePolicy(mode=mode)
```

- [ ] **Step 4: Add and run the package-level acceptance test**

Create `tests/acceptance/test_paper_only_package.py`:

```python
from gemini_trading.safety.execution_mode import load_runtime_policy


def test_no_supported_runtime_mode_allows_exchange_submission() -> None:
    for value in ("research", "paper"):
        policy = load_runtime_policy({"GEMINI_TRADING_MODE": value})
        assert policy.exchange_submission_allowed is False
```

Run:

```bash
uv run pytest tests/unit/safety/test_execution_mode.py tests/acceptance/test_paper_only_package.py -v
uv run pyright
```

Expected result: all tests and strict typing pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/safety/execution_mode.py tests/unit/safety/test_execution_mode.py tests/acceptance/test_paper_only_package.py
git commit -m "feat(safety): enforce paper-only runtime modes"
```

---

### Task 5: Encode the Version 0 Defects as Passing Regression Guards

**Files:**
- Create: `src/gemini_trading/safety/regression_guards.py`
- Create: `tests/regression/test_version0_guards.py`

**Interfaces:**
- Produces: `Regime`, `CandleCompletionError`, `DuplicateDecisionError`, `OrderValidationError`, `parse_regime()`, `require_closed_candle()`, `build_future_regime_labels()`, `DecisionRegistry`, `validate_sell_to_close()`, and `validate_price_geometry()`.

- [ ] **Step 1: Write the failing regression suite**

Create `tests/regression/test_version0_guards.py`:

```python
from decimal import Decimal

import pytest

from gemini_trading.safety.regression_guards import (
    CandleCompletionError,
    DecisionRegistry,
    DuplicateDecisionError,
    OrderValidationError,
    Regime,
    build_future_regime_labels,
    parse_regime,
    require_closed_candle,
    validate_price_geometry,
    validate_sell_to_close,
)


def test_trending_down_identity_is_preserved() -> None:
    assert parse_regime("Trending Down") is Regime.TRENDING_DOWN
    assert parse_regime("Trending Up") is Regime.TRENDING_UP


def test_incomplete_candle_is_rejected() -> None:
    with pytest.raises(CandleCompletionError):
        require_closed_candle("0")


def test_trailing_rows_without_future_outcomes_are_unlabeled() -> None:
    labels = build_future_regime_labels(
        closes=[Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103")],
        horizon=2,
        threshold=Decimal("0.005"),
    )

    assert labels[-2:] == [None, None]


def test_duplicate_decision_key_is_rejected() -> None:
    registry = DecisionRegistry()
    registry.register("BTC-USDT:15m:2026-07-21T08:00:00Z:baseline-v1")

    with pytest.raises(DuplicateDecisionError):
        registry.register("BTC-USDT:15m:2026-07-21T08:00:00Z:baseline-v1")


def test_sell_to_close_requires_an_eligible_position() -> None:
    with pytest.raises(OrderValidationError):
        validate_sell_to_close(position_quantity=Decimal("0"), requested_quantity=Decimal("0.1"))


def test_long_geometry_requires_stop_below_entry_and_target_above_entry() -> None:
    with pytest.raises(OrderValidationError):
        validate_price_geometry(
            side="long",
            entry=Decimal("100"),
            stop=Decimal("101"),
            target=Decimal("103"),
        )


def test_short_geometry_requires_target_below_entry_and_stop_above_entry() -> None:
    with pytest.raises(OrderValidationError):
        validate_price_geometry(
            side="short",
            entry=Decimal("100"),
            stop=Decimal("99"),
            target=Decimal("97"),
        )
```

- [ ] **Step 2: Run the suite and verify failure**

```bash
uv run pytest tests/regression/test_version0_guards.py -v
```

Expected result: FAIL because `regression_guards.py` is absent.

- [ ] **Step 3: Implement the pure safety guards**

Create `src/gemini_trading/safety/regression_guards.py`:

```python
"""Pure guards that prevent known Version 0 failure modes."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal


class Regime(StrEnum):
    RANGING = "Ranging"
    TRENDING_UP = "Trending Up"
    TRENDING_DOWN = "Trending Down"


class CandleCompletionError(ValueError):
    """Raised when a closed-candle workflow receives an incomplete candle."""


class DuplicateDecisionError(ValueError):
    """Raised when a deterministic decision identity is reused."""


class OrderValidationError(ValueError):
    """Raised when an order request violates a safety invariant."""


def parse_regime(value: str) -> Regime:
    normalized = " ".join(value.strip().split())
    try:
        return Regime(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported regime: {value!r}") from exc


def require_closed_candle(confirm: str) -> None:
    if confirm != "1":
        raise CandleCompletionError("Closed-candle workflows require confirm='1'.")


def build_future_regime_labels(
    closes: list[Decimal],
    horizon: int,
    threshold: Decimal,
) -> list[Regime | None]:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if threshold <= 0:
        raise ValueError("threshold must be positive")

    labels: list[Regime | None] = []
    for index, close in enumerate(closes):
        future_index = index + horizon
        if future_index >= len(closes):
            labels.append(None)
            continue
        if close <= 0:
            raise ValueError("close prices must be positive")

        future_return = closes[future_index] / close - Decimal("1")
        if future_return > threshold:
            labels.append(Regime.TRENDING_UP)
        elif future_return < -threshold:
            labels.append(Regime.TRENDING_DOWN)
        else:
            labels.append(Regime.RANGING)
    return labels


class DecisionRegistry:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def register(self, decision_key: str) -> None:
        if not decision_key.strip():
            raise ValueError("decision_key must not be empty")
        if decision_key in self._keys:
            raise DuplicateDecisionError(decision_key)
        self._keys.add(decision_key)


def validate_sell_to_close(
    position_quantity: Decimal,
    requested_quantity: Decimal,
) -> None:
    if requested_quantity <= 0:
        raise OrderValidationError("requested quantity must be positive")
    if position_quantity <= 0:
        raise OrderValidationError("sell-to-close requires an eligible long position")
    if requested_quantity > position_quantity:
        raise OrderValidationError("sell-to-close quantity exceeds the open position")


def validate_price_geometry(
    side: Literal["long", "short"],
    entry: Decimal,
    stop: Decimal,
    target: Decimal,
) -> None:
    if min(entry, stop, target) <= 0:
        raise OrderValidationError("entry, stop, and target must be positive")
    if side == "long" and not stop < entry < target:
        raise OrderValidationError("long geometry requires stop < entry < target")
    if side == "short" and not target < entry < stop:
        raise OrderValidationError("short geometry requires target < entry < stop")
```

- [ ] **Step 4: Run regression and property-focused validation**

```bash
uv run pytest tests/regression/test_version0_guards.py -v
uv run ruff check src/gemini_trading/safety/regression_guards.py tests/regression/test_version0_guards.py
uv run pyright
```

Expected result: all commands pass. The suite proves the new foundation cannot reproduce the seven specified Version 0 failures represented in this phase: regime truncation, incomplete candles, false trailing labels, duplicate decisions, invalid sell-to-close, invalid long geometry, and invalid short geometry.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/safety/regression_guards.py tests/regression/test_version0_guards.py
git commit -m "test(regression): prevent known prototype failure modes"
```

---

### Task 6: Enforce Tracked-File Repository Policy

**Files:**
- Create: `src/gemini_trading/safety/repository_policy.py`
- Create: `tests/unit/safety/test_repository_policy.py`

**Interfaces:**
- Produces: `RepositoryPolicyViolation` and `validate_tracked_paths(paths: Iterable[str])`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/safety/test_repository_policy.py`:

```python
import pytest

from gemini_trading.safety.repository_policy import (
    RepositoryPolicyViolation,
    validate_tracked_paths,
)


def test_safe_paths_are_allowed() -> None:
    validate_tracked_paths([".env.example", "src/gemini_trading/__init__.py"])


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "service.key",
        "certificate.pem",
        "__pycache__/module.pyc",
        "q_table.json",
    ],
)
def test_prohibited_tracked_paths_are_rejected(path: str) -> None:
    with pytest.raises(RepositoryPolicyViolation):
        validate_tracked_paths([path])
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/unit/safety/test_repository_policy.py -v
```

Expected result: FAIL because the module is absent.

- [ ] **Step 3: Implement repository policy validation**

Create `src/gemini_trading/safety/repository_policy.py`:

```python
"""Policy for paths that may be tracked in the public repository."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath


class RepositoryPolicyViolation(ValueError):
    """Raised when a prohibited path is tracked."""


_PROHIBITED_NAMES = {".env", ".env.local", "q_table.json", "config.json"}
_PROHIBITED_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".pyc"}


def validate_tracked_paths(paths: Iterable[str]) -> None:
    violations: list[str] = []
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        if raw_path == ".env.example":
            continue
        if path.name in _PROHIBITED_NAMES:
            violations.append(raw_path)
            continue
        if path.suffix.lower() in _PROHIBITED_SUFFIXES:
            violations.append(raw_path)
            continue
        if "__pycache__" in path.parts:
            violations.append(raw_path)

    if violations:
        joined = ", ".join(sorted(violations))
        raise RepositoryPolicyViolation(f"Prohibited tracked paths: {joined}")
```

- [ ] **Step 4: Add a CI-compatible invocation and verify**

Run:

```bash
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; paths=subprocess.check_output(['git','ls-files'], text=True).splitlines(); validate_tracked_paths(paths)"
uv run pytest tests/unit/safety/test_repository_policy.py -v
uv run pyright
```

Expected result: all commands pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/safety/repository_policy.py tests/unit/safety/test_repository_policy.py
git commit -m "security: enforce public repository file policy"
```

---

### Task 7: Add Local Secret and Quality Gates

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.secrets.baseline`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`

**Interfaces:**
- Consumes: package commands and repository policy from Tasks 3 and 6.
- Produces: repeatable local validation before commits.

- [ ] **Step 1: Create the pre-commit configuration**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
        args: ["--maxkb=1024"]
      - id: check-merge-conflict
      - id: check-toml
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.4
    hooks:
      - id: ruff-check
        args: ["--fix"]
      - id: ruff-format
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]
```

- [ ] **Step 2: Generate the secret baseline after sanitization**

```bash
uv run detect-secrets scan --all-files > .secrets.baseline
uv run detect-secrets audit .secrets.baseline
```

Expected result: every finding is manually reviewed; no active credential is marked as acceptable.

- [ ] **Step 3: Create `SECURITY.md`**

```markdown
# Security Policy

## Supported Code

Only the reconstructed package under `src/gemini_trading/` is supported. `legacy/prototype_v0/` is historical evidence and must not be deployed.

## Reporting

Do not open a public issue containing a credential, exploit details, private logs, or personal data. Contact the repository owner privately and include only the minimum information needed to reproduce the concern.

## Secret Exposure

An exposed credential is rotated before source or Git-history cleanup. The replacement is stored outside Git with least privilege. Public documentation never includes token values or private incident evidence.

## Trading Safety

The public package supports research and paper modes only. Any code path that enables demo or live exchange submission is a security-sensitive change requiring separate design approval, independent risk review, automated validation, and rollback documentation.
```

- [ ] **Step 4: Create `CONTRIBUTING.md` and run all hooks**

```markdown
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
```

Run:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Expected result: all hooks pass after applying any deterministic formatting fixes.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml .secrets.baseline SECURITY.md CONTRIBUTING.md
git commit -m "security: add local secret and quality gates"
```

---

### Task 8: Add GitHub CI, Dependency Updates, and Pull-Request Governance

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`
- Create: `.github/pull_request_template.md`
- Create: `.github/CODEOWNERS`
- Create: `docs/architecture/adr/0001-paper-only-reconstruction-foundation.md`

**Interfaces:**
- Consumes: all local validation commands from earlier tasks.
- Produces: pull-request checks and governance evidence.

- [ ] **Step 1: Create the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
        with:
          version: "0.8.0"
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: uv sync --all-groups --frozen
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run pyright
      - run: uv run pytest
      - run: uv run python -m build
      - run: uv run pip-audit
      - name: Validate tracked-file policy
        run: >-
          uv run python -c "import subprocess;
          from gemini_trading.safety.repository_policy import validate_tracked_paths;
          validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines())"
      - name: Scan working tree for secrets
        run: uv run detect-secrets scan --all-files --baseline .secrets.baseline

  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Before committing, verify referenced action versions against their official repositories and update only when the replacement major version is documented as compatible.

- [ ] **Step 2: Create Dependabot configuration**

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

- [ ] **Step 3: Create pull-request template and CODEOWNERS**

Create `.github/pull_request_template.md`:

```markdown
## Change

Describe the smallest independently reviewable behavior changed by this pull request.

## Evidence

- [ ] Failing test added before implementation.
- [ ] `uv run pre-commit run --all-files` passes.
- [ ] `uv run pytest` passes.
- [ ] `uv run pyright` passes.
- [ ] Package build passes.

## Trading and Risk Impact

- [ ] No exchange submission capability added.
- [ ] No risk limit weakened.
- [ ] No random allocation added to an execution-capable path.
- [ ] No private strategy parameter, dataset, model artifact, or credential added.

## Security Impact

Describe secret, dependency, data-access, and privilege implications.

## Rollback

State the exact commit or configuration action required to reverse this change.
```

Create `.github/CODEOWNERS`:

```text
* @muhamedsohaib
/.github/ @muhamedsohaib
/src/gemini_trading/safety/ @muhamedsohaib
/docs/operations/ @muhamedsohaib
```

- [ ] **Step 4: Record the architecture decision**

Create `docs/architecture/adr/0001-paper-only-reconstruction-foundation.md`:

```markdown
# ADR 0001: Paper-Only Reconstruction Foundation

- Status: Accepted
- Date: 2026-07-21

## Context

The public prototype exposed an administrative database credential, lacked automated validation, mixed research terminology with unvalidated behavior, and contained defects that could produce unsafe decisions.

## Decision

The project is reconstructed as an installable package. The public runtime supports only research and paper modes. The original prototype is quarantined as non-importable historical evidence. Secrets are prohibited, CI is mandatory, and known Version 0 defects are represented by passing regression tests.

## Consequences

- Demo and live execution require a separate approved design and promotion process.
- Existing prototype entry points are no longer supported.
- Pull requests must pass security, typing, test, and build gates.
- Repository history may be rewritten to remove exposed credentials.
```

- [ ] **Step 5: Commit and confirm CI starts**

```bash
git add .github docs/architecture/adr/0001-paper-only-reconstruction-foundation.md
git commit -m "ci: enforce reconstruction quality and governance gates"
git push origin design/hybrid-open-core-reconstruction
```

Expected result: the pull request shows both `quality` and `gitleaks` jobs. Any failure must be fixed before proceeding.

---

### Task 9: Configure Protected-Branch Governance

**Files:**
- Modify through GitHub repository settings: default branch protection and security settings.
- Update: `docs/operations/security-incident-2026-07-21.md` only if the final verification changes the public conclusion.

**Interfaces:**
- Consumes: passing CI workflow from Task 8.
- Produces: enforceable pull-request-only changes and active repository security features.

- [ ] **Step 1: Enable repository security features**

Enable dependency graph, Dependabot alerts, Dependabot security updates, secret scanning, and push protection where available for the repository plan and visibility.

Expected result: GitHub repository security settings show each available feature enabled.

- [ ] **Step 2: Protect `main`**

Create a branch ruleset for `main` with these requirements:

- Pull request required before merge.
- At least one approval required.
- Approval dismissed when new commits are pushed.
- Conversation resolution required.
- Required checks: `quality` and `gitleaks`.
- Branch must be up to date before merge.
- Force pushes disabled.
- Deletions disabled.
- Administrators included in the ruleset.

- [ ] **Step 3: Restrict sensitive changes through CODEOWNERS review**

Require code-owner review for paths covered by `.github/CODEOWNERS`.

Expected result: changes to CI, safety code, and operations documentation cannot merge without owner review.

- [ ] **Step 4: Verify direct pushes are rejected**

Attempt a harmless direct push to `main` from a disposable local commit without opening a pull request.

Expected result: GitHub rejects the push. Reset the disposable local commit afterward; do not bypass the rule.

- [ ] **Step 5: Record settings evidence privately**

Save screenshots or exported ruleset metadata in the private operations evidence store. Public documentation records only that protection is enabled, not administrative account details.

---

### Task 10: Produce the Foundation Verification Report

**Files:**
- Create: `reports/security/foundation-verification.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all previous tasks and passing GitHub checks.
- Produces: immutable evidence that the repository is secret-free, paper-only, buildable, tested, and governed.

- [ ] **Step 1: Run the complete local verification sequence**

```bash
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines())"
git log -p --all | grep -E 'SUPABASE_SERVICE_ROLE_KEY|service_role|eyJ[a-zA-Z0-9_-]+\.'
```

Expected result: all quality commands pass; the final history search returns no active secret value.

- [ ] **Step 2: Verify unsafe modes fail closed**

```bash
GEMINI_TRADING_MODE=live uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"
```

Expected result: process exits non-zero with `UnsafeExecutionModeError` and no network call occurs.

- [ ] **Step 3: Create the verification report**

Create `reports/security/foundation-verification.md`:

```markdown
# Security and Engineering Foundation Verification

- Verification date: 2026-07-21
- Repository: `muhamedsohaib/gemini-trading`
- Scope: security containment, paper-only enforcement, engineering foundation, CI, and governance

## Results

| Control | Result |
|---|---|
| Exposed Supabase credential rotated | Pass |
| Old credential confirmed invalid | Pass |
| Secret-bearing current files removed | Pass |
| Git history scan contains no active secret | Pass |
| Prototype quarantined outside executable package | Pass |
| Research and paper are the only accepted runtime modes | Pass |
| Exchange submission allowed by public runtime | No |
| Version 0 defect regression tests | Pass |
| Formatting and linting | Pass |
| Strict type checking | Pass |
| Unit, regression, and acceptance tests | Pass |
| Package build | Pass |
| Dependency audit | Pass |
| Secret scanning | Pass |
| Protected `main` branch | Pass |

## Known Limitations

This milestone does not implement market-data normalization, backtesting, strategy execution, portfolio accounting, risk sizing, exchange adapters, or claims of market edge. Those remain blocked behind later approved plans.

## Promotion Decision

The repository may proceed to the domain-contract and canonical-data design phase. It remains `RESEARCH_ONLY` and paper-only.
```

Do not mark any row `Pass` until the corresponding command, dashboard control, or credential check has been observed successfully.

- [ ] **Step 4: Replace `README.md` with the public project boundary**

Create or replace `README.md`:

```markdown
# Gemini Trading

Gemini Trading is a hybrid open-core research and paper-execution platform under controlled reconstruction.

## Current Status

- Promotion level: `RESEARCH_ONLY`
- Supported execution modes: `research`, `paper`
- Exchange order submission: disabled
- Profitability: not established

## Public Core

The repository will contain canonical market-data contracts, deterministic research tools, baseline strategies, portfolio and risk primitives, paper execution, testing, security controls, and reproducible benchmark evidence.

Private strategy parameters, trained proprietary artifacts, production credentials, production infrastructure, and investor-only evidence are excluded.

## Safety

The current package fails closed when configured for demo, live, production, or an unknown mode. Historical prototype code is preserved under `legacy/prototype_v0/` and is not supported for execution.

## Development

```bash
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run pytest
uv run pyright
```

See `docs/superpowers/specs/2026-07-21-hybrid-open-core-reconstruction-design.md` for the approved architecture.
```

- [ ] **Step 5: Run final checks, commit, and request review**

```bash
uv run pre-commit run --all-files
uv run pytest
uv run pyright
git add README.md reports/security/foundation-verification.md
git commit -m "docs: verify secure paper-only reconstruction foundation"
git push origin design/hybrid-open-core-reconstruction
```

Expected result: GitHub CI passes, the draft pull request contains only approved foundation work, and the verification report contains no unsupported pass claim.

---

## Plan Self-Review

### Spec coverage

- Credential rotation, log review, incident documentation, and history sanitization: Tasks 1–2.
- Prototype preservation without executable authority: Task 2.
- Installable package, locked environment, formatting, typing, tests, and build: Task 3.
- Paper-only fail-closed runtime: Task 4.
- First known-defect regression suite: Task 5.
- Tracked-file and secret policy: Tasks 6–7.
- CI, dependency scanning, security scanning, ADRs, PR governance: Task 8.
- Protected branch and GitHub security controls: Task 9.
- Reproducible final evidence and explicit scope limitations: Task 10.

### Deferred to later approved plans

- Full immutable domain contracts.
- Canonical OKX market-data provider and storage.
- Event-driven backtester.
- Deterministic baseline strategy.
- Portfolio accounting and independent risk governor.
- Paper broker and order state machine.
- Model reconstruction, validation, and drift monitoring.
- Demo or live execution of any kind.

### Consistency check

All executable code in this plan lives under `src/gemini_trading/`. Runtime policy supports only `ExecutionMode.RESEARCH` and `ExecutionMode.PAPER`. The regression guard names used in tests match their implementation signatures. No task introduces exchange credentials, exchange-order APIs, random allocation, or private strategy material.