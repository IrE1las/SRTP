"""Initialize server-only data before exposing the application."""
import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import main
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

main.on_startup()
runpy.run_path(str(Path('scripts/seed_local_data.py')), run_name='__main__')
with SessionLocal() as db:
    admin = db.query(User).filter_by(username='admin', role='admin').one()
    # Only bootstrap a newly created server database; never reset an existing admin.
    if not Path('/app/.runtime/ecs-initialized').exists():
        admin.password_hash = get_password_hash(os.environ['SRTP_INITIAL_ADMIN_PASSWORD'])
        admin.token_version += 1
        db.commit()
        Path('/app/.runtime/ecs-initialized').touch()
print('Server initialization complete.')
