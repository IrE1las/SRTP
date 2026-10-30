"""Explicit S6 migration preserves S5 history and fails closed before startup writes."""
import sqlite3
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.services import s6_migration as migration


def old_database(tmp_path):
    path = tmp_path / 's5.db'
    engine = create_engine('sqlite:///' + path.as_posix())
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for model in reversed(migration.MODELS):
            model.__table__.drop(connection)
        connection.exec_driver_sql("INSERT INTO users (id,username,password_hash,role,is_active,token_version,contact_failures,contact_locked) VALUES (21,'retained','unchanged','teacher',1,0,0,0)")
        connection.exec_driver_sql("INSERT INTO exams (id,owner_id,status,revision,name,classes) VALUES (8,21,'draft',1,'旧考试','[]')")
    return path, engine


def test_preview_backup_preserves_all_old_tables_and_repeat_noop(tmp_path):
    path, engine = old_database(tmp_path)
    before = path.read_bytes(); hashes = migration.fingerprints(path)
    assert set(migration.migrate(path)['missing_tables']) == migration.TABLES
    assert path.read_bytes() == before
    with pytest.raises(RuntimeError, match='S6'):
        migration.require_grade_schema(engine)
    result = migration.migrate(path, True)
    assert result['applied'] and result['preserved_original_tables']
    assert migration.fingerprints(path) == hashes
    with sqlite3.connect(result['backup']) as db:
        assert db.execute('SELECT username,password_hash FROM users').fetchall() == [('retained', 'unchanged')]
        assert db.execute('SELECT name FROM exams').fetchall() == [('旧考试',)]
        assert not migration.TABLES & {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    migration.require_grade_schema(engine)
    assert not migration.migrate(path, True)['applied']
    engine.dispose()


def test_failure_rolls_back_all_new_tables_and_preserves_backup(tmp_path, monkeypatch):
    path, engine = old_database(tmp_path)
    hashes = migration.fingerprints(path)
    def fail(*args, **kwargs):
        raise RuntimeError('simulated DDL failure')
    monkeypatch.setattr(migration.MODELS[1].__table__, 'create', fail)
    with pytest.raises(RuntimeError, match='simulated DDL'):
        migration.migrate(path, True)
    assert not migration.TABLES & set(inspect(engine).get_table_names())
    assert migration.fingerprints(path) == hashes
    engine.dispose()


def test_existing_database_blocks_startup_until_explicit_upgrade(tmp_path, monkeypatch):
    import main
    path, engine = old_database(tmp_path)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'SessionLocal', factory)
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match='S6'):
        main.on_startup()
    assert path.read_bytes() == before
    migration.migrate(path, True)
    main.on_startup(); main.on_startup()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT name FROM exams').fetchall() == [('旧考试',)]
        assert db.execute("SELECT COUNT(*) FROM users WHERE username='retained'").fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM exam_grades').fetchone()[0] == 0
    engine.dispose()


def test_partial_malformed_table_is_not_silently_accepted_or_patched(tmp_path):
    path, engine = old_database(tmp_path)
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE exam_grades (session_id TEXT PRIMARY KEY)')
    with pytest.raises(RuntimeError, match='结构不完整'):
        migration.require_grade_schema(engine)
    with pytest.raises(RuntimeError, match='结构不完整'):
        migration.migrate(path, True)
    engine.dispose()


def test_fresh_empty_database_starts_with_grade_schema(tmp_path, monkeypatch):
    import main
    engine = create_engine('sqlite:///' + (tmp_path / 'fresh.db').as_posix())
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'SessionLocal', sessionmaker(bind=engine))
    migration.require_grade_schema(engine)
    main.on_startup(); main.on_startup()
    assert migration.TABLES <= set(inspect(engine).get_table_names())
    migration.require_grade_schema(engine)
    assert main.health_check()['stage'] == 'S6'
    engine.dispose()
