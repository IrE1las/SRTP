"""S5 additive upgrades, backups, startup blocking and fresh/repeated startup."""
import sqlite3
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.services.s5_migration import TABLES, migrate, old_fingerprints, require_exam_schema


def test_preview_backup_preservation_and_idempotence(tmp_path):
    path = tmp_path / 's4.db'
    engine = create_engine('sqlite:///' + path.as_posix())
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for name in ['exam_control_events', 'exam_attempts', 'exam_participants', 'exams']:
            conn.exec_driver_sql('DROP TABLE ' + name)
        conn.exec_driver_sql("INSERT INTO users (id,username,password_hash,role,is_active,token_version,contact_failures,contact_locked) VALUES (21,'retained','unchanged','teacher',1,0,0,0)")
        conn.exec_driver_sql("INSERT INTO operation_questions (id,owner_id,disabled) VALUES (8,21,0)")
    before = path.read_bytes(); fingerprints = old_fingerprints(path)
    assert set(migrate(path)['missing_tables']) == TABLES
    assert path.read_bytes() == before
    with pytest.raises(RuntimeError, match='S5'):
        require_exam_schema(engine)
    report = migrate(path, apply=True)
    assert report['preserved_original_tables'] and report['applied']
    assert old_fingerprints(path) == fingerprints
    with sqlite3.connect(report['backup']) as conn:
        assert conn.execute('SELECT username,password_hash FROM users').fetchall() == [('retained', 'unchanged')]
        assert not TABLES.intersection(row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    require_exam_schema(engine)
    assert not migrate(path, apply=True)['applied']
    engine.dispose()


def test_new_install_and_repeated_startup(tmp_path, monkeypatch):
    import main
    from app.models import User
    from app.models.exam import Exam
    engine = create_engine('sqlite:///' + (tmp_path / 'fresh.db').as_posix())
    factory = sessionmaker(bind=engine)
    require_exam_schema(engine)
    monkeypatch.setattr(main, 'engine', engine); monkeypatch.setattr(main, 'SessionLocal', factory)
    main.on_startup()
    assert TABLES <= set(inspect(engine).get_table_names())
    with factory() as db:
        user = db.query(User).one()
        db.add(Exam(owner_id=user.id, name='持久草稿'))
        db.commit()
    main.on_startup()
    with factory() as db:
        assert db.query(Exam).one().name == '持久草稿'
        assert db.query(User).count() == 1
    engine.dispose()
