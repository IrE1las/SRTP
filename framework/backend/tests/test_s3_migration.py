import sqlite3
import pytest
from sqlalchemy import create_engine, inspect
from app.core.database import Base
from app.services.s3_migration import TABLES, migrate, old_fingerprints, require_operation_schema


def test_s3_preview_backup_repeat_and_old_data_preservation(tmp_path):
    path = tmp_path / 'previous-s2.db'
    engine = create_engine('sqlite:///' + path.as_posix())
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for table in ['operation_events','operation_sessions','operation_versions','operation_questions']:
            conn.exec_driver_sql('DROP TABLE ' + table)
        conn.exec_driver_sql("INSERT INTO users (id, username, password_hash, role, is_active, token_version, contact_failures, contact_locked) VALUES (15,'retained','hash-value','student',1,0,0,0)")
        conn.commit()
    before = path.read_bytes()
    preview = migrate(path)
    assert set(preview['missing_tables']) == TABLES
    assert path.read_bytes() == before
    with pytest.raises(RuntimeError, match='S3'):
        require_operation_schema(engine)
    before_rows = old_fingerprints(path)
    result = migrate(path, apply=True)
    assert result['preserved_original_tables']
    assert old_fingerprints(path) == before_rows
    with sqlite3.connect(result['backup']) as conn:
        assert conn.execute('SELECT username FROM users WHERE id=15').fetchone() == ('retained',)
    require_operation_schema(engine)
    assert not migrate(path, apply=True)['applied']
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_fresh_database_can_bootstrap_without_migration(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'fresh.db').as_posix())
    require_operation_schema(engine)
    Base.metadata.create_all(engine)
    require_operation_schema(engine)
    engine.dispose()


def test_two_real_startups_keep_s3_questions_and_sessions(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.models import User
    from app.models.operation import OperationQuestion, OperationVersion, OperationSession
    from app.services.operation_runtime import pack
    from app.services.operations import station_version
    from app.services.simulation_console.reference_runtime import ReferenceSimulationService
    from app.services.simulation_console.reference_station import reference_station_package
    import main
    engine = create_engine('sqlite:///' + (tmp_path / 'startup.db').as_posix())
    factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with factory() as db:
        user = User(username='startup-admin', password_hash='synthetic-no-login', role='admin')
        db.add(user); db.flush()
        q = OperationQuestion(owner_id=user.id)
        db.add(q); db.flush()
        v = OperationVersion(question_id=q.id, number=1, title='保留的录制', classes=['一班'],
            initial={'interval_available':True,'occupied_sections':[]}, station_version=station_version(),
            standard_log=[{'synthetic':'startup preservation only'}])
        db.add(v); db.flush()
        simulator = ReferenceSimulationService(reference_station_package())
        snap = simulator.new_session(user.id)
        db.add(OperationSession(id=snap['session_id'], version_id=v.id, owner_id=user.id,
            kind='preview', engine_state=pack(simulator, snap['session_id']), initial_snapshot=v.initial,
            station_version=station_version(), context={'pending':{'type':'SWITCH_TOTAL_NORMAL','expires_at':9999999999}}))
        db.commit()
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'SessionLocal', factory)
    main.on_startup()
    main.on_startup()
    with factory() as db:
        assert db.query(OperationQuestion).count() == 1
        assert db.query(OperationSession).one().context['pending']['type'] == 'SWITCH_TOTAL_NORMAL'
        assert db.query(OperationVersion).one().standard_log == [{'synthetic':'startup preservation only'}]
        assert db.query(User).count() == 1
    engine.dispose()
