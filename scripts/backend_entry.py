"""An absolute script path identifies this checkout's server in Windows processes."""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "framework" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(sys.argv[1]))
