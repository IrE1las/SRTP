"""Preview or explicitly apply S2 account migration with all services stopped."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.s2_migration import migrate_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Back up then apply; default is read-only preview')
    args = parser.parse_args()
    print(json.dumps(migrate_database(args.database, apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
