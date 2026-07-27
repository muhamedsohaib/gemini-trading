"""Route the remaining Task 10 preparation call through the memoized module function."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
test_anchor = "def test_prepare_does_not_materialize_final_phase(tmp_path: Path) -> None:\n"
if text.count(test_anchor) != 1:
    raise SystemExit("unexpected prepare-test anchor")
before, after = text.split(test_anchor, 1)
call = "    preparation = build_candidate_preparation(\n"
if after.count(call) != 1:
    raise SystemExit("unexpected prepare-test preparation call")
after = after.replace(
    call,
    "    preparation = sealed_evaluator.build_candidate_preparation(\n",
    1,
)
path.write_text(before + test_anchor + after, encoding="utf-8")
