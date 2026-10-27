"""Initialize only the reviewed sources and six theory topics, without legacy seeds."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import Base, engine, SessionLocal
from app.services.bootstrap import seed_theory
from app.services.s1_migration import require_current_schema
import app.models

def main():
    require_current_schema(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        print(json.dumps(seed_theory(db), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
