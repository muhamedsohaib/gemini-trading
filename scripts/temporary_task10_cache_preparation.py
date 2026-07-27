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
if text.count("    build_candidate_preparation,\n") != 1:
    raise SystemExit("unexpected build preparation import")
text = text.replace(
    "    build_candidate_preparation,\n",
    "    CandidatePreparation,\n",
    1,
)
import_anchor = '''from gemini_trading.strategy.sealed_evaluator import (
    CandidatePreparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
'''
if text.count(import_anchor) != 1:
    raise SystemExit("unexpected sealed evaluator import anchor")
text = text.replace(
    import_anchor,
    import_anchor
    + '''from gemini_trading.strategy.sealed_evaluator import (
    build_candidate_preparation as build_candidate_preparation_unbounded,
)
''',
    1,
)
fixture_anchor = '''@pytest.fixture(autouse=True)
def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
'''
cache_block = '''@pytest.fixture(autouse=True)
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

'''
if text.count(fixture_anchor) != 1:
    raise SystemExit("unexpected bounded integration fixture anchor")
text = text.replace(fixture_anchor, cache_block, 1)
monkeypatch_anchor = '''    monkeypatch.setattr(
        sealed_evaluator,
        "build_split_plan",
        _bounded_split_plan,
    )
'''
if text.count(monkeypatch_anchor) != 1:
    raise SystemExit("unexpected split-plan monkeypatch anchor")
text = text.replace(
    monkeypatch_anchor,
    monkeypatch_anchor
    + '''    monkeypatch.setattr(
        sealed_evaluator,
        "build_candidate_preparation",
        cached_candidate_preparation,
    )
''',
    1,
)
if text.count("    preparation = build_candidate_preparation(\n") != 1:
    raise SystemExit("unexpected explicit preparation call")
path.write_text(
    text.replace(
        "    preparation = build_candidate_preparation(\n",
        "    preparation = sealed_evaluator.build_candidate_preparation(\n",
        1,
    ),
    encoding="utf-8",
)
