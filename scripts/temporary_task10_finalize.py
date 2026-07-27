"""Apply the final Task 10 test correction before focused verification."""

from pathlib import Path


path = Path("tests/unit/strategy/test_pre_final.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from dataclasses import replace\n", "")
old = '''def test_pre_final_rejects_reordered_row_identity(tmp_path: Path) -> None:
    handoff = _handoff(tmp_path)
    reordered = replace(
        handoff,
        excluded_provider_rows=tuple(reversed(handoff.excluded_provider_rows)),
    )

    with pytest.raises((PreFinalArtifactError, ValueError), match=r"order|identity"):
        _artifacts(tmp_path, reordered)
'''
new = '''def test_pre_final_rejects_reordered_row_identity(tmp_path: Path) -> None:
    handoff = _handoff(tmp_path)
    artifacts = _artifacts(tmp_path, handoff)
    files = dict(artifacts.files)
    manifest = json.loads(files["pre-final-manifest.json"])
    rows = manifest["excluded_provider_rows"]
    assert isinstance(rows, list)
    manifest["excluded_provider_rows"] = list(reversed(rows))
    files["pre-final-manifest.json"] = canonical_json_bytes(manifest)

    result = json.loads(files["pre-final-result-manifest.json"])
    core_names = tuple(
        name
        for name in REQUIRED_PRE_FINAL_NAMES
        if name != "pre-final-result-manifest.json"
    )
    result["artifacts"] = [
        [name, hashlib.sha256(files[name]).hexdigest()]
        for name in sorted(core_names)
    ]
    files["pre-final-result-manifest.json"] = canonical_json_bytes(result)
    tampered = PreFinalArtifacts(
        artifacts.pre_final_id,
        tuple((name, files[name]) for name in REQUIRED_PRE_FINAL_NAMES),
    )

    with pytest.raises(PreFinalArtifactError, match="excluded provider rows mismatch"):
        verify_pre_final_artifacts(tampered, expected_handoff=handoff)
'''
if text.count(old) != 1:
    raise SystemExit("unexpected reordered-row test structure")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
