"""Check all locked distributions and native imports without relying on a hash marker."""
import importlib
import importlib.metadata
import sys
from pathlib import Path


def main():
    failures = []
    for raw in Path(sys.argv[1]).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        try:
            actual = importlib.metadata.version(name)
            if actual != expected:
                failures.append(f"{name}: expected {expected}, found {actual}")
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{name}: missing")
    for module in ("fastapi", "uvicorn", "sqlalchemy", "pydantic_core", "bcrypt", "cryptography", "jiter"):
        try:
            importlib.import_module(module)
        except Exception as exc:
            failures.append(f"{module}: {type(exc).__name__}: {exc}")
    for failure in failures:
        print(failure)
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
