"""Import already readable teaching sources into the local managed library.

Run with the backend environment, e.g. python scripts/import_knowledge.py path/to/course.pptx.
Encrypted files can be uploaded with a password through the administrator UI.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from app.core.database import engine, SessionLocal
from app.models.knowledge import KnowledgeDocument, KnowledgeMigration
from app.services.knowledge_library import add, adopt_builtin


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--description', default='')
    args = parser.parse_args()
    KnowledgeDocument.__table__.create(engine, checkfirst=True)
    KnowledgeMigration.__table__.create(engine, checkfirst=True)
    with SessionLocal() as db:
        adopt_builtin(db)
        for path in args.files:
            try:
                result = add(db, path.name, path.read_bytes(), description=args.description)
                print(f'{path.name}: {result["page_count"]}{result["unit"]}, {result["text_chars"]} characters')
            except HTTPException as failure:
                if failure.status_code != 409:
                    raise
                print(f'{path.name}: already imported')


if __name__ == '__main__':
    main()
