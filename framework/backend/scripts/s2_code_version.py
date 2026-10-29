"""Print the reproducible S2 code/test/dependency/retained-source digest."""
import json
import hashlib

from s1_code_version import ROOT, code_version


def s2_code_version():
    version = code_version()
    # S2 live acceptance also repairs launcher/stop behavior; include those entry points.
    for name in ('启动项目.ps1', '停止项目.ps1', '启动项目.bat', 'launch.ps1'):
        version['files'][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    version['files'] = dict(sorted(version['files'].items()))
    raw = json.dumps(version['files'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')
    version['file_count'] = len(version['files'])
    version['sha256'] = hashlib.sha256(raw).hexdigest()
    return version


if __name__ == '__main__':
    print(json.dumps(s2_code_version(), ensure_ascii=False, indent=2))
