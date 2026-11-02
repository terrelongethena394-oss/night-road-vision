from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'release_manifest.json').read_text(encoding='utf-8'))
for row in data['files']:
 p=root/row['path']
 assert p.is_file() and p.stat().st_size==row['bytes'],row['path']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],row['path']
print('PASS',len(data['files']),'files; ABI32 workbench / ABI30 SD')
