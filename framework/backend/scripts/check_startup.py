"""Read-only startup schema check; never migrates or opens a browser."""
import argparse
import os
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    path = args.database.resolve()
    print('Database: ' + str(path), flush=True)
    if not path.exists():
        print('New database: normal application startup will initialize it.', flush=True)
        return 0
    os.environ['DATABASE_URL'] = 'sqlite:///' + path.as_posix()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core.database import engine
    from app.services.s1_migration import require_current_schema
    from app.services.s2_migration import require_account_schema
    from app.services.s3_migration import require_operation_schema
    try:
        require_current_schema(engine)
        require_account_schema(engine)
        require_operation_schema(engine)
    except RuntimeError as exc:
        print(str(exc), flush=True)
        return 2
    finally:
        engine.dispose()
    print('Database schema is ready for S3.', flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
