from pathlib import Path
import json, sys, tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monitor import snapshot, compare
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory);(root/'settings.conf').write_text('mode=original')
 before=snapshot(root)
 (root/'settings.conf').write_text('mode=modified');(root/'new.txt').write_text('synthetic')
 result=compare(before,snapshot(root));print(json.dumps(result,indent=2))
