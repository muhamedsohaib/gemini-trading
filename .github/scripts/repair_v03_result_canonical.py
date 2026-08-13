from pathlib import Path

path = Path("src/gemini_trading/strategy/qualification_artifacts_v0_3.py")
text = path.read_text()
needle = '''    if hashlib.sha256(canonical_json_bytes(structural)).hexdigest() != qualification_id:
        raise StudyArtifactError("v0.3 qualification structural identity changed")
    files = tuple(sorted((*core, (_RESULT, result_raw))))
'''
replacement = '''    if hashlib.sha256(canonical_json_bytes(structural)).hexdigest() != qualification_id:
        raise StudyArtifactError("v0.3 qualification structural identity changed")
    expected_result = canonical_json_bytes(
        {
            "schema_version": _SCHEMA,
            "qualification_id": qualification_id,
            "classification": classification.value,
            "inventory_root_sha256": root_sha,
            "artifacts": _inventory_payload(core),
        }
    )
    if result_raw != expected_result:
        raise StudyArtifactError("v0.3 qualification result canonical bytes changed")
    files = tuple(sorted((*core, (_RESULT, result_raw))))
'''
if needle not in text:
    raise SystemExit("canonical result patch anchor missing")
path.write_text(text.replace(needle, replacement))
