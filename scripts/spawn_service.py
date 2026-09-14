"""Start a hidden service with literal Windows paths and durable log handles.

PowerShell 5.1 Start-Process resolves brackets in working/log paths as wildcards.
The already prepared project Python can pass these paths directly to Windows.
"""
import os
from pathlib import Path
import subprocess
import sys


def main():
    executable, entry, directory, stdout_path, stderr_path, *arguments = sys.argv[1:]
    with Path(stdout_path).open("wb") as output, Path(stderr_path).open("wb") as errors:
        process = subprocess.Popen(
            [executable, entry, *arguments],
            cwd=directory,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=errors,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    print(process.pid)


if __name__ == "__main__":
    main()
