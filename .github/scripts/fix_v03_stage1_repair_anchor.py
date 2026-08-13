from pathlib import Path

path = Path(".github/scripts/repair_v03_stage1.py")
text = path.read_text()
old = '''replace_once(
    execution,
    \'\'\'    handoff: DatasetHandoffManifest,\\n\'\'\',
    \'\'\'    handoff: V03DatasetHandoffManifest,\\n\'\'\',
)
'''
new = '''target = Path(execution)
text = target.read_text()
old_annotation = "    handoff: DatasetHandoffManifest,\\n"
if text.count(old_annotation) != 2:
    raise SystemExit("expected exactly two v0.3 handoff annotations")
target.write_text(text.replace(old_annotation, "    handoff: V03DatasetHandoffManifest,\\n"))
'''
if old not in text:
    raise SystemExit("v0.3 annotation repair block missing")
path.write_text(text.replace(old, new, 1))
