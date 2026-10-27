"""Test fixtures independent of public registration and removed exercise modules."""
import json
from pathlib import Path
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models import User
from app.services.shunting_data import import_reviewed_routes
from main import app

def auth_headers(client, username, role):
    provider = app.dependency_overrides[get_db]()
    db = next(provider)
    try:
        db.add(User(username=username, password_hash=get_password_hash('password123'), role=role,
                    real_name=username, student_id=username+'-id' if role=='student' else None,
                    class_name='信号一班' if role=='student' else None))
        db.commit()
    finally:
        provider.close()
    response = client.post('/api/auth/login', json={'username':username,'password':'password123'})
    assert response.status_code == 200, response.text
    return {'Authorization':f"Bearer {response.json()['access_token']}"}

def _import_payload(db):
    root = Path(__file__).resolve().parents[3]
    import_reviewed_routes(db, json.loads((root / 'ai_design/station/shunting_interlocking_reviewed.json').read_text('utf8')))
    db.commit()
