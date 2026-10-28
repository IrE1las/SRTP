"""Print a reproducible digest of S3 source, tests and retained station inputs."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def manifest():
    files = set()
    for relative in ['framework/backend/app', 'framework/backend/scripts', 'framework/backend/tests',
                     'framework/frontend/src', 'framework/frontend/tests', 'ai_design/station']:
        for path in (ROOT / relative).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.js', '.vue', '.mjs', '.json', '.md', '.csv', '.txt'}:
                files.add(path)
    for relative in ['framework/backend/main.py', 'framework/backend/requirements.lock.txt',
                     'framework/frontend/package.json', 'framework/frontend/package-lock.json',
                     'framework/frontend/vite.config.js', '启动项目.ps1', '停止项目.ps1', 'AGENTS.md']:
        files.add(ROOT / relative)
    hashes = {path.relative_to(ROOT).as_posix():sha256(path.read_bytes()).hexdigest() for path in sorted(files)}
    digest = sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'stage':'S3', 'file_count':len(hashes), 'sha256':digest, 'files':hashes}


if __name__ == '__main__':
    print(json.dumps(manifest(), ensure_ascii=False, indent=2))
