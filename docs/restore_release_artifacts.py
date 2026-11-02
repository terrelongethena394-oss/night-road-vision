from pathlib import Path
import json,hashlib,urllib.request
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'docs/published_artifacts.json').read_text(encoding='utf-8'))
for row in data['files']:
 path=root/row['path']
 if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']:
  print('OK',row['path']);continue
 path.parent.mkdir(parents=True,exist_ok=True)
 with urllib.request.urlopen(row['download_url'],timeout=180) as response:
  content=response.read()
 assert len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256'],row['path']
 path.write_bytes(content)
 print('RESTORED',row['path'])
print('Run python docs/verify_release.py to check the complete snapshot.')
