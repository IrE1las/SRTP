"""Read-only delivery audit; reports names/counts, never credentials or user rows."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
TEXT_SUFFIXES = {'.py', '.js', '.mjs', '.vue', '.css', '.json', '.md', '.txt', '.ps1', '.bat', '.html', '.sql', '.toml', '.yaml', '.yml', '.example'}
REMOVED = [
    'framework/frontend/src/features/modules',
    'framework/frontend/src/views/student/ExerciseLobby.vue',
    'framework/frontend/src/views/student/ExerciseWorkbench.vue',
    'framework/frontend/src/views/student/ExerciseHistory.vue',
    'framework/frontend/src/views/student/ExerciseReplay.vue',
    'framework/frontend/src/views/student/ClassicExam.vue',
    'framework/frontend/src/views/student/ShuntingQuestionBank.vue',
    'framework/backend/app/api/module_one_experiment1.py',
    'framework/backend/app/services/module_one',
    'framework/backend/app/models/module_one.py',
]
FINAL_DOCS = ['README.md', '接管与使用说明.md', '管理员出题与批阅使用说明.md',
              '项目内容大纲.md', '实验专题题库说明.md', '验收文档/S7_代码验证记录.md',
              '验收文档/S7_待办与未验证事项.md', '验收文档/S7_前端设计复核.md']


def audit():
    issues = []
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf8').split('\0')
    tracked = [name for name in tracked if name]
    local = []
    for name in tracked:
        path = Path(name)
        if (any(part in {'.runtime', '.backups', '__pycache__', 'node_modules', 'vector_db'} for part in path.parts)
                or path.suffix in {'.db', '.sqlite', '.sqlite3'}
                or (('.env' in path.name) and not path.name.endswith('.example'))):
            local.append(name)
    if local:
        issues.append({'tracked_local_artifacts': local})
    credentials = set()
    for relative in ['framework/backend/.env', 'ai/key.env']:
        path = ROOT / relative
        if not path.exists():
            continue
        for line in path.read_text('utf8').splitlines():
            match = re.match(r'\s*([A-Z_]*(?:KEY|SECRET|TOKEN)[A-Z_]*)\s*=\s*(.*?)\s*$', line)
            if match:
                value = match[2].strip('\'"')
                if len(value) >= 16 and not any(word in value.lower() for word in ['replace-with', 'your-key', 'example']):
                    credentials.add(value)
    exposed = []
    scanned = 0
    # Include unstaged S7 additions as well as the current Git index.
    deliverable = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode('utf8').split('\0')
    for name in sorted(set(deliverable) - {''}):
        path = ROOT / name
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or path.stat().st_size > 5_000_000:
            continue
        text = path.read_text('utf8', errors='replace')
        scanned += 1
        if (re.search(r'\bsk-[A-Za-z0-9_-]{24,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text)
                or any(value in text for value in credentials)):
            exposed.append(name)
    if exposed:
        issues.append({'credential_literal_paths': exposed})
    existing = [name for name in REMOVED if (ROOT / name).exists()]
    if existing:
        issues.append({'removed_implementations_still_present': existing})
    for name in ['style.css', 'readability.css']:
        text = (ROOT / 'framework/frontend/src' / name).read_text('utf8')
        if re.search(r'\.(?:classic-exam-page|editor-page|grading-page|question-bank)\b', text):
            issues.append({'retired_css': name})
    contract = json.loads((ROOT / 'framework/backend/tests/fixtures/s1_retained_contract.json').read_text('utf8'))
    changed = [name for name, expected in contract['sources'].items()
               if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    if changed:
        issues.append({'retained_source_mismatch': changed})
    missing_links = []
    for name in FINAL_DOCS:
        path = ROOT / name
        if not path.exists():
            missing_links.append(name)
            continue
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text('utf8')):
            if re.match(r'^(?:[a-z]+:|#)', target, re.I):
                continue
            relative = unquote(target.split('#')[0].strip('<>'))
            if relative and not (path.parent / relative).is_file():
                missing_links.append(name + ': ' + relative)
    if missing_links:
        issues.append({'missing_final_document_links': missing_links})
    code = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sorted(set(deliverable) - {''})
            if (name.startswith(('framework/', 'tools/reference_simulator/', 'ai_design/station/'))
                or name in {'启动项目.ps1', '启动项目.bat', '停止项目.ps1', 'launch.ps1'})
            and (ROOT / name).is_file()}
    manifest = hashlib.sha256(json.dumps(code, ensure_ascii=False, sort_keys=True).encode('utf8')).hexdigest()
    return {'ok': not issues, 'code_file_count': len(code), 'code_manifest_sha256': manifest,
            'tracked_file_count': len(tracked), 'text_files_scanned': scanned,
            'protected_source_count': len(contract['sources']), 'tracked_local_artifacts': len(local),
            'credential_literal_matches': len(exposed), 'issues': issues,
            'history_scan_performed': False, 'browser_validation_performed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit()
    if args.output:
        path = args.output.resolve()
        if not path.is_relative_to(ROOT / '.runtime'):
            parser.error('报告只能写入项目 .runtime 目录')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
