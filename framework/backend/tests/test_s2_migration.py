"""Upgrade/rollback checks on synthetic old account tables, never the business database."""
import json
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.services.s2_migration import migrate_database, require_account_schema


@pytest.fixture()
def old_db(tmp_path):
    path = tmp_path / 's1-accounts.db'
    with sqlite3.connect(path) as conn:
        conn.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT,
                real_name TEXT, role TEXT, student_id TEXT, class_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE lab_attempts(id INTEGER PRIMARY KEY, student_id INTEGER REFERENCES users(id), answers JSON);
            INSERT INTO users(id,username,password_hash,role,student_id) VALUES(4,'old-student','old-hash','student',NULL);
            INSERT INTO users(id,username,password_hash,real_name,role,student_id,class_name)
                VALUES(7,'old-complete','old-hash-2','原姓名','student','OLD-7','原班级');
            INSERT INTO lab_attempts VALUES(9,4,'{"answer":"原作答"}');
            INSERT INTO lab_attempts VALUES(10,7,'{"answer":"原作答2"}');
        ''')
    return path


def rows(path):
    with sqlite3.connect(path) as conn:
        return {r[0]: conn.execute(f'SELECT * FROM "{r[0]}"').fetchall() for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def test_preview_startup_stop_and_apply_preserve_old_values_and_ids(old_db, tmp_path):
    original_bytes, original_rows = old_db.read_bytes(), rows(old_db)
    preview = migrate_database(old_db)
    assert preview['backup'] is None
    assert set(preview['missing_user_columns']) == {'email', 'phone', 'is_active', 'token_version', 'contact_failures', 'contact_locked'}
    assert old_db.read_bytes() == original_bytes
    engine = create_engine(f'sqlite:///{old_db.as_posix()}')
    try:
        with pytest.raises(RuntimeError, match='S2旧结构.*启动已停止且未修改数据库'):
            require_account_schema(engine)
        assert old_db.read_bytes() == original_bytes
        report = migrate_database(old_db, apply=True, backup_dir=tmp_path / 'backups')
        assert report['preserved_original_fields']
        assert rows(report['backup']) == original_rows
        require_account_schema(engine)
        with sqlite3.connect(old_db) as conn:
            assert conn.execute('SELECT id,email,phone,is_active,token_version FROM users ORDER BY id').fetchall() == [
                (4,None,None,1,0), (7,None,None,1,0)]
            assert conn.execute('SELECT contact_failures,contact_locked FROM users').fetchall() == [(0,0),(0,0)]
            snapshot = json.loads(conn.execute('SELECT identity_snapshot FROM lab_attempts WHERE id=10').fetchone()[0])
            assert snapshot['student_name'] == '原姓名' and snapshot['class_name'] == '原班级'
            assert snapshot['source'] == 'migration_current_identity'
            missing = json.loads(conn.execute('SELECT identity_snapshot FROM lab_attempts WHERE id=9').fetchone()[0])
            assert missing['student_name'] is missing['student_number'] is missing['class_name'] is None
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO users(id,student_id) VALUES(8,'OLD-7')")
        before_repeat = rows(old_db)
        assert migrate_database(old_db, apply=True, backup_dir=tmp_path / 'backups')['preserved_original_fields']
        assert rows(old_db) == before_repeat
    finally:
        engine.dispose()


@pytest.mark.parametrize('kind', ['duplicate', 'whitespace_duplicate', 'blank'])
def test_conflicting_old_numbers_are_reported_never_silently_changed(old_db, tmp_path, kind):
    value = {'duplicate': 'OLD-7', 'whitespace_duplicate': ' OLD-7 ', 'blank': ''}[kind]
    with sqlite3.connect(old_db) as conn:
        conn.execute('INSERT INTO users(id,student_id) VALUES(8,?)', (value,))
    before = old_db.read_bytes()
    preview = migrate_database(old_db)
    assert preview['duplicate_student_number_user_ids'] or preview['blank_student_number_user_ids']
    with pytest.raises(ValueError, match='不自动改号'):
        migrate_database(old_db, apply=True, backup_dir=tmp_path / 'backups')
    assert old_db.read_bytes() == before


def test_failure_rolls_back_alter_index_and_snapshot_and_keeps_backup(old_db, tmp_path):
    before = rows(old_db)
    with pytest.raises(RuntimeError, match='injected failure'):
        migrate_database(old_db, apply=True, backup_dir=tmp_path / 'backups', _fail_after_alter=True)
    assert rows(old_db) == before
    with sqlite3.connect(old_db) as conn:
        assert 'token_version' not in [r[1] for r in conn.execute('PRAGMA table_info(users)')]
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='ux_users_student_number_s2'").fetchone() is None
    assert rows(next((tmp_path / 'backups').glob('*.db'))) == before


def test_migration_rejects_missing_or_external_paths(tmp_path):
    with pytest.raises(ValueError, match='项目内已存在'):
        migrate_database(tmp_path / 'absent.db', apply=True)


def test_real_startup_refuses_s1_schema_before_seeding(old_db, monkeypatch):
    import main
    # This fixture only has user/answer tables, so S1 has no removed-feature migration to request.
    before = old_db.read_bytes()
    engine = create_engine(f'sqlite:///{old_db.as_posix()}')
    monkeypatch.setattr(main, 'engine', engine)
    try:
        with pytest.raises(RuntimeError, match='S2旧结构'):
            main.on_startup()
        assert old_db.read_bytes() == before
    finally:
        engine.dispose()
