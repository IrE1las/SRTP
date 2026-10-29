"""Static local-import and removed-route check; does not import the application."""
import ast
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[3]
BACKEND=ROOT/'framework/backend'
FRONTEND=ROOT/'framework/frontend/src'
errors=[]
checked=0

def module_exists(path):
    return path.with_suffix('.py').is_file() or (path/'__init__.py').is_file()

for directory in (BACKEND/'app',BACKEND/'scripts',BACKEND/'tests'):
    for path in directory.rglob('*.py'):
        checked+=1
        tree=ast.parse(path.read_text('utf8'),filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                if node.level:
                    base=path.parent
                    for _ in range(node.level-1):
                        base=base.parent
                    target=base.joinpath(*(node.module or '').split('.'))
                    if node.module and not module_exists(target):
                        errors.append(f'{path.relative_to(ROOT)}:{node.lineno}: {node.module}')
                elif node.module and node.module.split('.')[0] in {'app','tests'}:
                    if not module_exists(BACKEND.joinpath(*node.module.split('.'))):
                        errors.append(f'{path.relative_to(ROOT)}:{node.lineno}: {node.module}')
            elif isinstance(node,ast.Import):
                for name in node.names:
                    if name.name.startswith('app.') and not module_exists(BACKEND.joinpath(*name.name.split('.'))):
                        errors.append(f'{path.relative_to(ROOT)}:{node.lineno}: {name.name}')

pattern=re.compile(r"""(?:from\s*|import\s*\(\s*|import\s*)['"]([^'"]+)['"]""")
for path in FRONTEND.rglob('*'):
    if not path.is_file() or path.suffix not in {'.vue','.js'}:
        continue
    checked+=1
    source=path.read_text('utf8')
    for match in pattern.finditer(source):
        name=match.group(1).split('?')[0]
        if name.startswith('@/'):
            target=FRONTEND/name[2:]
        elif name.startswith('.'):
            target=(path.parent/name).resolve()
        else:
            continue
        if not any(p.is_file() for p in [target,target.with_suffix('.js'),target.with_suffix('.vue'),target/'index.js']):
            errors.append(f'{path.relative_to(ROOT)}: {name}')
    for obsolete in ('/student/modules','/student/lobby','/student/history','/student/interlocking-exam',
                     '/student/shunting-questions','/student/simulation-console','/teacher/exercises','/teacher/grading','/admin/grading'):
        if obsolete in source:
            errors.append(f'{path.relative_to(ROOT)}: removed route {obsolete}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'{checked} source files checked; no unresolved local imports or removed frontend routes.')
