"""Windows integration check using a source-only copy and PATH without Python/Node.

Run with a development Python: python scripts/verify_launch.py DESTINATION
DESTINATION must be a new directory inside this repository's .planning folder.
Leaves logs and the disposable copy for review; never stops the source checkout.
"""
import hashlib
import ctypes
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = Path(sys.argv[1]).resolve()
if not DEST.is_relative_to(ROOT / ".planning") or DEST.exists():
    raise SystemExit("Use a NEW directory under this repository's .planning folder.")
git = shutil.which("git")
if not git:
    raise SystemExit("Git is required to create the source-only test fixture.")
paths = subprocess.check_output([git, "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]).decode().split("\0")
DEST.mkdir(parents=True)
for name in filter(None, paths):
    source = ROOT / name
    if source.is_file():
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

system = Path(os.environ["SystemRoot"]) / "System32"
ps = system / "WindowsPowerShell" / "v1.0" / "powershell.exe"
env = os.environ.copy()
env.update(PATH=f"{system};{ps.parent};{os.environ['SystemRoot']}", SRTP_NO_PAUSE="1")
for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX", "NODE_OPTIONS", "SECRET_KEY", "DATABASE_URL", "DEEPSEEK_API_KEY"):
    env.pop(name, None)
results = []


def run_bat(label, stop=False, offline=False, expected=0):
    print(f"[verify] {label}", flush=True)
    local_env = dict(env, SRTP_OFFLINE="1" if offline else "0")
    name = "停止项目.bat" if stop else "启动项目.bat"
    arguments = "" if stop else " -NoBrowser"
    command = f'"{system / "cmd.exe"}" /d /s /c ""{DEST / name}"{arguments}"'
    with (DEST.parent / f"{DEST.name}-{label}.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, env=local_env, cwd=DEST.parent, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
    assert completed.returncode == expected, f"{label}: exit {completed.returncode}; inspect its log"
    results.append({"test": label, "exit": completed.returncode})


def state():
    return json.loads((DEST / ".runtime/services-v2.json").read_text(encoding="utf-8"))


def pids():
    return [[p["pid"] for p in s["processes"]] for s in state()["services"]]


def check_web():
    services = {s["name"]: s for s in state()["services"]}
    base = f'http://127.0.0.1:{services["frontend"]["port"]}'
    with urllib.request.urlopen(base + "/api/health", timeout=5) as response:
        assert json.load(response)["service"] == "railway-interlocking-api"
    request = urllib.request.Request(base + "/api/auth/login", json.dumps({"username": "admin", "password": "00000000"}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
        assert result["user"]["role"] == "admin" and result["access_token"]
    with urllib.request.urlopen(base + "/", timeout=5) as response:
        assert b"<html" in response.read().lower()


def data_counts():
    with sqlite3.connect(DEST / "framework/backend/railway.db") as database:
        tables = [r[0] for r in database.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: database.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


def check_stopped():
    for service in state()["services"]:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{service["port"]}/api/health', timeout=2)
        except OSError:
            continue
        raise AssertionError(f'{service["name"]} is still serving after stop')


try:
    assert not (DEST / ".runtime").exists()
    assert not (DEST / "framework/frontend/node_modules").exists()
    assert not (DEST / "framework/backend/.env").exists()
    run_bat("cold-online")
    check_web()
    installed = json.loads((DEST / ".runtime/environment-v2.json").read_text())
    assert Path(installed["python"]).is_relative_to(DEST / ".runtime")
    assert Path(installed["node"]).is_relative_to(DEST / ".runtime")
    assert subprocess.check_output([installed["python"], "-c", "import platform; print(platform.python_version())"], env=env).strip() == b"3.12.14"
    initial_pids = pids()
    original_counts = data_counts()
    assert any("lab_question" in t and n > 0 for t, n in original_counts.items())
    secret_hash = hashlib.sha256((DEST / "framework/backend/.env").read_bytes()).hexdigest()
    run_bat("warm-reuse", offline=True)
    assert pids() == initial_pids
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(DEST / ".runtime/launch-v2.lock"), 0xC0000000, 0, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        run_bat("concurrent-start-rejected", offline=True, expected=1)
        assert pids() == initial_pids
    finally:
        kernel.CloseHandle(handle)
    run_bat("stop", stop=True)
    check_stopped()
    run_bat("offline-restart", offline=True)
    check_web()
    assert data_counts() == original_counts
    assert hashlib.sha256((DEST / "framework/backend/.env").read_bytes()).hexdigest() == secret_hash
    run_bat("stop-before-update", stop=True)
    lock = DEST / "framework/backend/requirements.lock.txt"
    lock.write_bytes(lock.read_bytes() + b"\n# integration test: lock changed\n")
    frontend_lock = DEST / "framework/frontend/package-lock.json"
    frontend_lock.write_bytes(frontend_lock.read_bytes() + b"\n")
    run_bat("lock-update-offline", offline=True)
    check_web()
    run_bat("stop-before-repair", stop=True)
    interpreter = Path(installed["python"])
    interpreter.rename(interpreter.with_suffix(".exe.missing-test"))
    run_bat("repair-missing-python", offline=True)
    check_web()
    assert data_counts() == original_counts
    run_bat("stop-before-failure", stop=True)
    backend_main = DEST / "framework/backend/main.py"
    original_main = backend_main.read_bytes()
    backend_main.write_bytes(b"raise RuntimeError('intentional launcher verification failure')\n" + original_main)
    try:
        run_bat("backend-failure-cleanup", offline=True, expected=1)
        check_stopped()
    finally:
        backend_main.write_bytes(original_main)
    run_bat("recover-after-failure", offline=True)
    check_web()
    results.append({"test": "web-proxy-login-seed-preservation", "passed": True, "tables": original_counts})
finally:
    if (DEST / ".runtime/services-v2.json").exists():
        run_bat("final-stop", stop=True)
    (DEST.parent / f"{DEST.name}-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
