"""Memoize deterministic Candidate preparation inside the Task 10 integration fixture."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from gemini_trading.research.dataset_reader import VerifiedDataset\n",
    "from gemini_trading.research.config import SimulationConfig\n"
    "from gemini_trading.research.dataset_reader import VerifiedDataset\n",
    1,
)
old_import = '''from gemini_trading.strategy.sealed_evaluator import (
    build_candidate_preparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
'''
new_import = '''from gemini_trading.strategy.sealed_evaluator import (
    CandidatePreparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
from gemini_trading.strategy.sealed_evaluator import (
    build_candidate_preparation as build_candidate_preparation_unbounded,
)
'''
if text.count(old_import) != 1:
    raise SystemExit("unexpected sealed evaluator import block")
text = text.replace(old_import, new_import, 1)
old_fixture = '''@pytest.fixture(autouse=True)
def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_split_plan",
        _bounded_split_plan,
    )
'''
new_fixture = '''@pytest.fixture(autouse=True)
def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    preparation_cache: dict[bool, CandidatePreparation] = {}

    def cached_candidate_preparation(
        *,
        dataset: VerifiedDataset,
        simulation: SimulationConfig,
        initial_cash: Decimal,
        include_final: bool,
    ) -> CandidatePreparation:
        cached = preparation_cache.get(include_final)
        if cached is None:
            cached = build_candidate_preparation_unbounded(
                dataset=dataset,
                simulation=simulation,
                initial_cash=initial_cash,
                include_final=include_final,
            )
            preparation_cache[include_final] = cached
        return cached

    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_split_plan",
        _bounded_split_plan,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_candidate_preparation",
        cached_candidate_preparation,
    )
'''
if text.count(old_fixture) != 1:
    raise SystemExit("unexpected bounded integration fixture")
text = text.replace(old_fixture, new_fixture, 1)
old_call = '''    preparation = build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        include_final=False,
    )
'''
new_call = '''    preparation = sealed_evaluator.build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        include_final=False,
    )
'''
if text.count(old_call) != 1:
    raise SystemExit("unexpected explicit preparation call")
path.write_text(text.replace(old_call, new_call, 1), encoding="utf-8")
