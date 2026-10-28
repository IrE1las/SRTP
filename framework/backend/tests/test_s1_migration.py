"""Upgrade the exact old schema, preserving retained row bytes and IDs."""
import copy
import json
from pathlib import Path
import sqlite3
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import User, LabQuestion, LabAttempt, QuestionWorkspace, QuestionRevision, GradeDraft, GradeAudit
from app.services.bootstrap import seed_theory
from app.services.lab_topics import digest, evaluate
from app.services.s1_migration import migrate_database, require_current_schema, REMOVED_TABLES
from tests.test_lab_topics import completed

@pytest.fixture()
def legacy_db(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as conn:
        conn.executescript((Path(__file__).parent / 'fixtures/s1_legacy_schema.sql').read_text('utf8'))
    # S1 cleanup remains independently tested; provision S2 ORM fields before fixture seeding.
    from app.services.s2_migration import migrate_database as migrate_accounts
    migrate_accounts(path, apply=True, backup_dir=tmp_path / 'account-fixture-backups')
    engine = create_engine(f'sqlite:///{path.as_posix()}')
    with Session(engine) as db:
        seed_theory(db)
        user = User(username='migration-student', password_hash='fixture-only', role='student',
                    real_name=None, student_id=None, class_name=None)
        db.add(user)
        db.flush()
        questions = db.query(LabQuestion).all()
        for key,topic in [('lab-07-01',7),('lab-08-01',8),('custom-legacy',1)]:
            data = copy.deepcopy(questions[0].content)
            data.update(key=key,topic=topic)
            q = LabQuestion(key=key,topic=topic,sequence=1,dataset_id=questions[0].dataset_id,
                            content=data,fingerprint=digest(data))
            db.add(q)
            questions.append(q)
        db.flush()
        for q in questions:
            attempt = LabAttempt(question_id=q.id, student_id=user.id, question_snapshot=q.content,
                                 answers=completed(q), result=evaluate(q.content,completed(q)))
            db.add(attempt)
            db.flush()
            db.add(QuestionWorkspace(question_id=q.id))
            db.add(QuestionRevision(question_id=q.id,version=1,content=q.content,author_id=user.id))
            db.add(GradeDraft(attempt_id=attempt.id, reviewer_id=user.id,content={'scores':{}}))
            db.add(GradeAudit(attempt_id=attempt.id, reviewer_id=user.id,before={},after={}))
        db.commit()
    with sqlite3.connect(path) as conn:
        # Populate all removed tables from their exact legacy schema using type-correct synthetic values.
        conn.execute('PRAGMA foreign_keys=ON')
        order = ['stations','switches','signals','sections','interlocking_tables','device_states',
                 'route_states','exercises','exercise_sessions','operation_logs','ai_scores',
                 'shunting_questions','module_one_attempts','module_one_events']
        for table in order:
            foreign_keys = {r[3]:r[2] for r in conn.execute(f'PRAGMA foreign_key_list("{table}")')}
            data = {}
            for _, name, kind, required, default, primary in conn.execute(f'PRAGMA table_info("{table}")'):
                if default is not None or (not required and not primary):
                    continue
                if name in foreign_keys:
                    parent = foreign_keys[name]
                    data[name] = conn.execute(f'SELECT id FROM "{parent}" LIMIT 1').fetchone()[0]
                elif name == 'id' and kind.startswith('INTEGER'):
                    data[name] = 1
                elif kind.startswith(('INTEGER','FLOAT','BOOLEAN')):
                    data[name] = 1
                elif kind.startswith('JSON'):
                    data[name] = '{}'
                elif kind.startswith('DATETIME'):
                    data[name] = '2026-10-26 00:00:00'
                else:
                    data[name] = 's1-fixture'
            columns = ','.join('"'+k+'"' for k in data)
            values = ','.join('?' for k in data)
            conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({values})', tuple(data.values()))
        review = json.dumps({'scores':{'reason':8},'comment':'迁移前已有教师评语'},ensure_ascii=False)
        conn.execute('UPDATE lab_attempts SET review=?, reviewer_id=1, reviewed_at=? WHERE id=1',
                     (review,'2026-10-26 01:00:00'))
    engine.dispose()
    return path

def rows(path):
    with sqlite3.connect(path) as conn:
        return {r[0]:conn.execute('SELECT * FROM "'+r[0]+'"').fetchall()
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}

def test_preview_never_writes_and_startup_refuses_old_schema(legacy_db):
    before = legacy_db.read_bytes()
    result = migrate_database(legacy_db)
    assert result['mode'] == 'preview' and result['backup'] is None
    assert result['remove_questions'] == result['remove_attempts'] == 3
    assert result['retained']['lab_attempts']['count'] == 18
    assert legacy_db.read_bytes() == before
    engine = create_engine(f'sqlite:///{legacy_db.as_posix()}')
    try:
        with pytest.raises(RuntimeError, match='启动已停止且未修改数据库'):
            require_current_schema(engine)
    finally:
        engine.dispose()
    assert legacy_db.read_bytes() == before

def test_old_schema_migrates_with_exact_preservation_repeatability_and_backup(legacy_db, tmp_path):
    before = rows(legacy_db)
    report = migrate_database(legacy_db, apply=True, backup_dir=tmp_path / 'backups')
    assert report['preserved_exactly']
    assert rows(report['backup']) == before
    assert Path(report['manifest']).is_file()
    after = rows(legacy_db)
    assert not set(after).intersection(REMOVED_TABLES)
    assert after['users'] == before['users']
    for table in ['shunting_datasets','shunting_routes','feedback_snippets']:
        assert after[table] == before[table]
    for table in ['lab_questions','lab_attempts','question_workspaces','question_revisions','grade_drafts','grade_audits']:
        assert len(after[table]) == 18
        assert after[table] == before[table][:18]
    second = migrate_database(legacy_db, apply=True, backup_dir=tmp_path / 'backups')
    assert second['remove_questions'] == second['remove_attempts'] == 0
    assert second['removed_tables'] == {}
    assert rows(legacy_db) == after
    engine = create_engine(f'sqlite:///{legacy_db.as_posix()}')
    try:
        require_current_schema(engine)
        with Session(engine) as db:
            seed_theory(db)
    finally:
        engine.dispose()
    assert rows(legacy_db) == after

def test_failure_rolls_back_data_and_ddl_and_preserves_recoverable_backup(legacy_db,tmp_path):
    before = rows(legacy_db)
    with pytest.raises(RuntimeError,match='injected failure'):
        migrate_database(legacy_db,apply=True,backup_dir=tmp_path / 'backups',_fail_after_cleanup=True)
    assert rows(legacy_db) == before
    backup = next((tmp_path / 'backups').glob('*.db'))
    assert rows(backup) == before

def test_actual_application_startup_is_idempotent_in_an_isolated_empty_database(tmp_path, monkeypatch):
    import main
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    path = tmp_path / 'fresh.db'
    engine = create_engine(f'sqlite:///{path.as_posix()}')
    monkeypatch.setattr(main,'engine',engine)
    monkeypatch.setattr(main,'SessionLocal',sessionmaker(bind=engine))
    try:
        main.on_startup()
        first = rows(path)
        main.on_startup()
        assert rows(path) == first
        assert len(first['users']) == 1
        assert len(first['lab_questions']) == 18
        assert len(first['shunting_routes']) == 35
        assert not set(first).intersection(REMOVED_TABLES)
    finally:
        engine.dispose()

def test_migration_rejects_nonexistent_or_external_paths(tmp_path):
    with pytest.raises(ValueError,match='项目内已存在'):
        migrate_database(tmp_path / 'missing.db',apply=True)
