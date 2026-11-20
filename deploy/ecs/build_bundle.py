"""Package only application files and reviewed sources; exclude local secrets/data."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / '.runtime/ecs-deploy'
OUTPUT.mkdir(parents=True, exist_ok=True)
paths = set()
for directory in ('framework/backend/app', 'framework/backend/scripts', 'ai_design/station', 'deploy/ecs'):
    for path in (ROOT / directory).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.db'}:
            paths.add(path)
for name in ('framework/backend/main.py', 'framework/backend/requirements.lock.txt'):
    paths.add(ROOT / name)
references = json.loads((ROOT / 'ai_design/station/report_answer_references.json').read_text(encoding='utf8'))
blueprint = json.loads((ROOT / 'ai_design/station/report_topic_blueprint.json').read_text(encoding='utf8'))
for name in [x['path'] for x in references['sources']] + [x['source'] for x in blueprint['reports']]:
    paths.add(ROOT / name.replace('\\', '/'))
manifest = {}
with tarfile.open(OUTPUT / 'srtp-release.tar.gz', 'w:gz') as archive:
    archive.add(ROOT / 'deploy/ecs/dockerignore', arcname='.dockerignore')
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        assert path.is_file(), relative
        assert path.name != '.env' and path.suffix not in {'.db', '.env'}, relative
        archive.add(path, arcname=relative, recursive=False)
        manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((ROOT / 'framework/frontend/dist').rglob('*')):
        if path.is_file():
            relative = 'web/' + path.relative_to(ROOT / 'framework/frontend/dist').as_posix()
            archive.add(path, arcname=relative, recursive=False)
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
(OUTPUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
bundle = OUTPUT / 'srtp-release.tar.gz'
print(f'{bundle}: {bundle.stat().st_size} bytes; {len(manifest)} files')
print('SHA256:', hashlib.sha256(bundle.read_bytes()).hexdigest())
