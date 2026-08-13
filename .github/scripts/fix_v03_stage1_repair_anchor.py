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

stage1_path = Path("src/gemini_trading/strategy/v0_3_stage1.py")
stage1_text = stage1_path.read_text()
long_line = '''        if tuple(item.path for item in self.files) != tuple(sorted(item.path for item in self.files)):
'''
wrapped = '''        paths = tuple(item.path for item in self.files)
        if paths != tuple(sorted(paths)):
'''
if long_line not in stage1_text:
    raise SystemExit("v0.3 Stage 1 inventory-order anchor missing")
stage1_path.write_text(stage1_text.replace(long_line, wrapped, 1))
