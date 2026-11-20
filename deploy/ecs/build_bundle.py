"""Build a release from current files, excluding workstation data and secrets."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / '.runtime/ecs-sync-20261120'
OUTPUT.mkdir(parents=True, exist_ok=True)
files = set()
for directory in ('framework/backend/app', 'framework/backend/scripts', 'ai_design/station', 'deploy/ecs'):
    files.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                 and p.suffix not in {'.pyc', '.db', '.env'})
files.update(ROOT / x for x in ('framework/backend/main.py', 'framework/backend/requirements.lock.txt'))
for name, key in [('report_answer_references.json', 'sources'), ('report_topic_blueprint.json', 'reports'),
                  ('experiment_3_4_questions.json', 'reports')]:
    data = json.loads((ROOT / 'ai_design/station' / name).read_text(encoding='utf8'))
    for item in data[key]:
        files.add(ROOT / item.get('path', item.get('source')).replace('\\', '/'))
manifest = {}
bundle = OUTPUT / 'srtp-20261120.tar.gz'
with tarfile.open(bundle, 'w:gz') as archive:
    for path in sorted(files):
        relative = path.relative_to(ROOT).as_posix()
        assert path.is_file() and path.name != '.env' and path.suffix not in {'.db', '.env'}, relative
        archive.add(path, arcname=relative, recursive=False)
        manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((ROOT / 'framework/frontend/dist').rglob('*')):
        if path.is_file():
            relative = 'web/' + path.relative_to(ROOT / 'framework/frontend/dist').as_posix()
            archive.add(path, arcname=relative, recursive=False)
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
(OUTPUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'bundle': str(bundle), 'bytes': bundle.stat().st_size, 'files': len(manifest),
                  'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest()}))
