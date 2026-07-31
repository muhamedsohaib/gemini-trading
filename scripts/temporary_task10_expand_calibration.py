"""Preserve the final calibration sample without changing production rules."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
constants_old = "_MAX_CALIBRATION_ROWS = 500\n_MAX_DECISION_ROWS = 64\n"
constants_new = (
    "_MAX_CALIBRATION_ROWS = 1_000\n"
    "_MAX_DECISION_ROWS = 64\n"
    "_FINAL_CALIBRATION_ROWS = 512\n"
)
if text.count(constants_old) != 1:
    raise SystemExit("unexpected Task 10 calibration constants")
text = text.replace(constants_old, constants_new, 1)

folds_old = '''    folds = tuple(
        replace(
            fold,
            development_test_indices=fold.development_test_indices[:_MAX_DECISION_ROWS],
        )
        for fold in plan.folds[: policy.minimum_development_folds]
    )
'''
folds_new = '''    selected_folds = plan.folds[: policy.minimum_development_folds]
    folds = tuple(
        replace(
            fold,
            development_test_indices=fold.development_test_indices[
                : (
                    _FINAL_CALIBRATION_ROWS
                    if fold_index == len(selected_folds) - 1
                    else _MAX_DECISION_ROWS
                )
            ],
        )
        for fold_index, fold in enumerate(selected_folds)
    )
'''
if text.count(folds_old) != 1:
    raise SystemExit("unexpected Task 10 split fixture")
path.write_text(text.replace(folds_old, folds_new, 1), encoding="utf-8")
