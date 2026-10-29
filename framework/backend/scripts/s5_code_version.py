"""Print the S5 source/test/station manifest without loading application settings."""
import json
from hashlib import sha256
from s3_code_version import ROOT, manifest


if __name__ == '__main__':
    result = manifest()
    # Include styles and the governing plan in the reproducible source evidence.
    for path in (ROOT / 'framework/frontend/src').rglob('*.css'):
        result['files'][path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    for name in ['项目重构正式约束与分步验收计划.md', 'README.md']:
        result['files'][name] = sha256((ROOT / name).read_bytes()).hexdigest()
    result['file_count'] = len(result['files'])
    result['sha256'] = sha256(json.dumps(result['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result['stage'] = 'S5'
    # ASCII escapes keep redirected JSON valid on Windows legacy code pages.
    print(json.dumps(result, ensure_ascii=True, indent=2))
