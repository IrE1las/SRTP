"""S4 upgrade is additive, explicit, backed up and preserves S3 records."""
import sqlite3
import pytest
from sqlalchemy import create_engine, inspect
from app.core.database import Base
from app.services.s4_migration import TABLES, migrate, old_fingerprints, require_learning_schema


def test_s4_preview_backup_preservation_and_idempotence(tmp_path):
    path = tmp_path / 's3.db'
    engine = create_engine('sqlite:///' + path.as_posix())
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        for name in ['operation_reviews', 'operation_attempts']:
            connection.exec_driver_sql('DROP TABLE ' + name)
        connection.exec_driver_sql("INSERT INTO users (id,username,password_hash,role,is_active,token_version,contact_failures,contact_locked) VALUES (21,'retained','unchanged','teacher',1,0,0,0)")
        connection.exec_driver_sql("INSERT INTO operation_questions (id,owner_id,disabled) VALUES (8,21,0)")
        connection.commit()
    before = path.read_bytes()
    fingerprints = old_fingerprints(path)
    assert set(migrate(path)['missing_tables']) == TABLES
    assert before == path.read_bytes()
    with pytest.raises(RuntimeError, match='S4'):
        require_learning_schema(engine)
    report = migrate(path, apply=True)
    assert report['applied'] and report['preserved_original_tables']
    assert old_fingerprints(path) == fingerprints
    with sqlite3.connect(report['backup']) as connection:
        assert connection.execute('SELECT username,password_hash FROM users').fetchall() == [('retained', 'unchanged')]
        assert not TABLES.intersection(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    require_learning_schema(engine)
    assert not migrate(path, apply=True)['applied']
    engine.dispose()


def test_fresh_schema_and_two_startups_keep_learning_history(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.models import User
    from app.models.operation import OperationQuestion, OperationVersion, OperationSession
    from app.models.operation_learning import OperationAttempt, OperationReview
    from app.services import operations as ops
    import main
    engine = create_engine('sqlite:///' + (tmp_path / 'fresh.db').as_posix())
    require_learning_schema(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user = User(username='retained-admin', password_hash='no-login', role='admin')
        db.add(user); db.flush()
        question = OperationQuestion(owner_id=user.id)
        db.add(question); db.flush()
        version = OperationVersion(question_id=question.id, number=1, title='保留题设', initial={}, station_version=ops.station_version())
        db.add(version); db.flush()
        simulator = ops.ReferenceSimulationService(ops.reference_station_package())
        snapshot = simulator.new_session(user.id)
        sid = snapshot['session_id']
        db.add(OperationSession(id=sid, version_id=version.id, owner_id=user.id, kind='learning', status='submitted',
            engine_state=ops.persistent_state(simulator, sid), initial_snapshot={}, station_version=ops.station_version()))
        db.flush()
        db.add(OperationAttempt(session_id=sid, question_id=question.id, student_id=user.id, question_snapshot={'title':'旧题目'}, identity_snapshot={}, outcome={'score':100}))
        db.add(OperationReview(session_id=sid, comment='保留评语'))
        db.commit()
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'SessionLocal', factory)
    main.on_startup(); main.on_startup()
    with factory() as db:
        assert db.get(OperationAttempt, sid).outcome == {'score': 100}
        assert db.get(OperationReview, sid).comment == '保留评语'
        assert db.query(User).count() == 1
    engine.dispose()
