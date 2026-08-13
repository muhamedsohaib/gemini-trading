"""Contracts for Candidate v0.3 prospective-final sealing without market-row access."""

from __future__ import annotations

import hashlib
import inspect
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.entry_selectivity import EntrySelectivityPolicy
from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.prospective_seal_v0_3 import (
    V03LocalProspectiveFinalSealStore,
    create_v0_3_prospective_seal,
)
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_artifacts_v0_3 import (
    V03QualificationArtifactContext,
    V03QualificationArtifacts,
)

_FIXED_VERIFIED_AT = datetime(2026, 8, 13, 9, 45, tzinfo=UTC)


def _artifacts(
    classification: QualificationClassification = QualificationClassification.QUALIFIED,
) -> V03QualificationArtifacts:
    context = V03QualificationArtifactContext(
        code_commit="1" * 40,
        dataset_id="2" * 64,
        dataset_handoff_inventory_root="3" * 64,
        dataset_run_id=123,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )
    policy = serialize_candidate_policy(CandidatePolicy.locked_v0_3())
    selectivity = canonical_json_bytes(asdict(EntrySelectivityPolicy.locked_v0_3()))
    policy_sha = hashlib.sha256(policy).hexdigest()
    selectivity_sha = hashlib.sha256(selectivity).hexdigest()
    configuration = canonical_json_bytes(
        {
            "schema_version": "candidate-v0.3-qualification-config-v1",
            "dataset_id": context.dataset_id,
            "development_start": "2018-01-01T00:00:00Z",
            "development_end_exclusive": "2026-08-01T00:00:00Z",
            "initial_cash": "10000",
            "simulation_sha256": "6" * 64,
            "strategy_id": "candidate.multi_model.v0_3",
            "policy_version": "candidate-multi-model-v0.3",
            "selectivity_policy_sha256": selectivity_sha,
        }
    )
    manifest = canonical_json_bytes(
        {
            "schema_version": "candidate-v0.3-qualification-result-v1",
            "context": asdict(context),
            "policy_sha256": policy_sha,
            "selectivity_policy_sha256": selectivity_sha,
            "configuration_sha256": hashlib.sha256(configuration).hexdigest(),
            "development_plan_sha256": "7" * 64,
            "classification": classification.value,
        }
    )
    result = canonical_json_bytes(
        {
            "schema_version": "candidate-v0.3-qualification-result-v1",
            "qualification_id": "4" * 64,
            "classification": classification.value,
            "inventory_root_sha256": "5" * 64,
            "artifacts": [],
        }
    )
    files = tuple(
        sorted(
            (
                ("configuration.json", configuration),
                ("entry-selectivity-policy.json", selectivity),
                ("policy.json", policy),
                ("qualification-manifest.json", manifest),
                ("qualification-result.json", result),
            )
        )
    )
    return V03QualificationArtifacts(
        qualification_id="4" * 64,
        inventory_root_sha256="5" * 64,
        classification=classification,
        context=context,
        files=files,
    )


def test_qualified_v0_3_artifact_seals_first_strict_future_month_for_exactly_18_months(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gemini_trading.strategy.prospective_seal_v0_3 as module

    monkeypatch.setattr(module, "_verification_milestone_utc", lambda: _FIXED_VERIFIED_AT)
    seal = create_v0_3_prospective_seal(_artifacts())

    assert seal.strategy_id == "candidate.multi_model.v0_3"
    assert seal.policy_version == "candidate-multi-model-v0.3"
    assert seal.development_cutoff == datetime(2026, 8, 1, tzinfo=UTC)
    assert seal.bridge_start == datetime(2026, 8, 1, tzinfo=UTC)
    assert seal.final_start == datetime(2026, 9, 1, tzinfo=UTC)
    assert seal.final_end == datetime(2028, 3, 1, tzinfo=UTC)
    assert seal.bridge_end == seal.final_start
    assert seal.verified_at == _FIXED_VERIFIED_AT
    assert len(seal.policy_sha256) == 64
    assert len(seal.selectivity_policy_sha256) == 64


@pytest.mark.parametrize(
    "classification",
    [QualificationClassification.REJECTED, QualificationClassification.INCONCLUSIVE],
)
def test_nonqualified_v0_3_artifacts_cannot_seal(
    monkeypatch: pytest.MonkeyPatch,
    classification: QualificationClassification,
) -> None:
    import gemini_trading.strategy.prospective_seal_v0_3 as module

    monkeypatch.setattr(module, "_verification_milestone_utc", lambda: _FIXED_VERIFIED_AT)
    with pytest.raises(FinalAccessError, match="QUALIFIED"):
        create_v0_3_prospective_seal(_artifacts(classification))


def test_seal_rejects_source_or_dataset_identity_not_bound_to_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gemini_trading.strategy.prospective_seal_v0_3 as module

    monkeypatch.setattr(module, "_verification_milestone_utc", lambda: _FIXED_VERIFIED_AT)
    original = _artifacts()
    wrong_context = replace(original.context, code_commit="8" * 40, dataset_id="9" * 64)
    with pytest.raises(FinalAccessError, match="qualification context"):
        create_v0_3_prospective_seal(replace(original, context=wrong_context))


def test_seal_rejects_changed_selectivity_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    import gemini_trading.strategy.prospective_seal_v0_3 as module

    monkeypatch.setattr(module, "_verification_milestone_utc", lambda: _FIXED_VERIFIED_AT)
    original = _artifacts()
    mapping = dict(original.files)
    mapping["entry-selectivity-policy.json"] = canonical_json_bytes(
        {"primary_percentile": "0.80"}
    )
    with pytest.raises(FinalAccessError, match="selectivity"):
        create_v0_3_prospective_seal(replace(original, files=tuple(sorted(mapping.items()))))


def test_verification_timestamp_is_observed_not_a_cli_or_function_choice() -> None:
    assert "verified_at" not in inspect.signature(create_v0_3_prospective_seal).parameters


def test_v0_3_store_is_single_seal_and_contains_no_market_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gemini_trading.strategy.prospective_seal_v0_3 as module

    monkeypatch.setattr(module, "_verification_milestone_utc", lambda: _FIXED_VERIFIED_AT)
    store = V03LocalProspectiveFinalSealStore(tmp_path)
    seal = store.create(_artifacts())
    assert store.load(seal.seal_id) == seal
    with pytest.raises(FinalAccessError, match="already exists"):
        store.create(_artifacts())
    encoded = (
        tmp_path
        / "data"
        / "historical-validation"
        / "v0-3-prospective-final"
        / "seals"
        / seal.seal_id
        / "prospective-final-seal.json"
    ).read_text()
    assert "candles" not in encoded
    assert "prices" not in encoded
    assert "returns" not in encoded
