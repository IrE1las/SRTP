"""Print a reproducible digest for S1 code, tests, dependencies and retained sources."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SUFFIXES = {'.css', '.py', '.vue', '.js', '.mjs', '.json', '.sql', '.md', '.txt'}


def code_version():
    selected = set()
    for directory in ('framework/backend/app', 'framework/backend/scripts', 'framework/backend/tests',
                      'framework/frontend/src', 'framework/frontend/tests', 'ai_design/station',
                      'tools/reference_simulator'):
        selected.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and p.suffix in SUFFIXES)
    selected.update(ROOT / name for name in ('AGENTS.md', 'framework/backend/main.py',
                     'framework/backend/requirements.lock.txt', 'framework/frontend/package.json',
                     'framework/frontend/package-lock.json', 'framework/frontend/vite.config.js'))
    files = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(selected)}
    raw = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')
    return {
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT).decode().strip(),
        'branch':subprocess.check_output(['git','branch','--show-current'], cwd=ROOT).decode().strip(),
        'file_count':len(files), 'sha256':hashlib.sha256(raw).hexdigest(), 'files':files,
    }


if __name__ == '__main__':
    print(json.dumps(code_version(), ensure_ascii=False, indent=2))
