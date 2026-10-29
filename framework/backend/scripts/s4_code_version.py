"""Print the S4 source/test/station manifest without loading application settings."""
import json
from hashlib import sha256
from s3_code_version import ROOT, manifest


if __name__ == '__main__':
    result = manifest()
    # Browser fixes also change CSS; keep those files in the reproducible evidence.
    for path in (ROOT / 'framework/frontend/src').rglob('*.css'):
        result['files'][path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    result['file_count'] = len(result['files'])
    result['sha256'] = sha256(json.dumps(result['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result['stage'] = 'S4'
    print(json.dumps(result, ensure_ascii=False, indent=2))
