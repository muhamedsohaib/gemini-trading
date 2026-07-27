"""Use stored research result identities in the Task 10 sealed-chain integration test."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from dataclasses import replace\n",
    "from dataclasses import dataclass, replace\n",
    1,
)
anchor = "_MAX_DECISION_ROWS = 64\n\n\n"
insert = '''_MAX_DECISION_ROWS = 64


@dataclass(frozen=True, slots=True)
class _StoredResearchVerification:
    result_id: str


def _stored_research_verifier(
    root: Path,
    experiment_id: str,
) -> _StoredResearchVerification:
    manifest = cast(
        dict[str, object],
        json.loads(
            LocalResearchStore(root).read_artifact(
                experiment_id,
                "result-manifest.json",
            )
        ),
    )
    result_id = manifest.get("result_id")
    if not isinstance(result_id, str):
        raise AssertionError("stored research result identity is missing")
    return _StoredResearchVerification(result_id=result_id)


'''
if text.count(anchor) != 1:
    raise SystemExit("unexpected Task 10 constants anchor")
text = text.replace(anchor, insert, 1)
old = '''    verified = StrategyStudyVerificationService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
        research_strategy_reconstructor=reconstruct_study_strategy,
    ).verify(artifacts.study_id)
'''
new = '''    verified = StrategyStudyVerificationService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
        research_verifier=lambda experiment_id: _stored_research_verifier(
            tmp_path,
            experiment_id,
        ),
        research_strategy_reconstructor=reconstruct_study_strategy,
    ).verify(artifacts.study_id)
'''
if text.count(old) != 1:
    raise SystemExit("unexpected Task 10 verification call")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
