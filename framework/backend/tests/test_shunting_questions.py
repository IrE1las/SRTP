import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.shunting_route import ShuntingQuestion
from app.services.shunting_questions import build_answer_spec, generate_shunting_questions, parse_switches
from tests.test_exercise_api import auth_headers

PAYLOAD = Path(__file__).resolve().parents[3] / 'ai_design/station/shunting_interlocking_reviewed.json'


def _import_payload(db_session):
    from app.services.shunting_data import import_reviewed_routes

    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    import_reviewed_routes(db_session, payload)
    db_session.commit()


def _answer_from_spec(spec):
    return {
        'route_buttons': spec['route_buttons'],
        'switches': {item['code']: item['position'] for item in spec['switches']},
        'switch_roles': {item['code']: item['role'] for item in spec['switches']},
        'hostile_signals': [item['raw'] for item in spec['hostile_signals']],
        'track_sections': [item['raw'] for item in spec['track_sections']],
    }


def test_switch_parser_preserves_positions_and_bracket_roles():
    parsed = parse_switches('(9/11)、[13/15]、{23/25}、27')
    assert [(item['code'], item['position'], item['role']) for item in parsed] == [
        ('9/11', 'reverse', 'required'),
        ('13/15', 'normal', 'protective'),
        ('23/25', 'normal', 'driven'),
        ('27', 'normal', 'required'),
    ]


def test_question_generation_is_deterministic_and_lossless(db_session, seeded_station):
    _import_payload(db_session)
    result = generate_shunting_questions(db_session)
    db_session.commit()
    assert result == {'dataset_id': 1, 'inserted': 35, 'updated': 0, 'total': 35}
    assert db_session.query(ShuntingQuestion).count() == 35
    question = db_session.query(ShuntingQuestion).filter_by(question_key='original-station-shunting:34:v1').one()
    assert question.answer_spec['switches'][1] == {'code': '23/25', 'position': 'normal', 'role': 'driven', 'notation': '{23/25}'}
    again = generate_shunting_questions(db_session)
    db_session.commit()
    assert again == {'dataset_id': 1, 'inserted': 0, 'updated': 0, 'total': 35}


def test_question_api_separates_student_view_and_teacher_answer_key(client: TestClient, db_session, seeded_station):
    _import_payload(db_session)
    teacher = auth_headers(client, 'question_teacher', 'teacher')
    student = auth_headers(client, 'question_student', 'student')
    generated = client.post('/api/exam/shunting/questions/generate', headers=teacher)
    assert generated.status_code == 200
    assert generated.json()['inserted'] == 35

    listing = client.get('/api/exam/shunting/questions', headers=student)
    assert listing.status_code == 200
    assert len(listing.json()) == 35
    first = listing.json()[0]
    assert first['route_number'] == 20
    assert 'answer_spec' not in first
    detail = client.get(f"/api/exam/shunting/questions/{first['id']}", headers=student)
    assert detail.status_code == 200
    assert 'answer_spec' not in detail.json()
    assert detail.json()['options']['switches']
    assert client.get(f"/api/exam/shunting/questions/{first['id']}/answer", headers=student).status_code == 403
    answer_response = client.get(f"/api/exam/shunting/questions/{first['id']}/answer", headers=teacher)
    assert answer_response.status_code == 200
    answer_payload = answer_response.json()
    assert answer_payload['answer_spec']['route_buttons'] == ['D1A', 'D7A']
    assert answer_payload['source_fields']['道岔'] == '(1/3)'

    wrong = client.post(f"/api/exam/shunting/questions/{first['id']}/submit", headers=student, json={})
    assert wrong.status_code == 200
    assert wrong.json()['all_correct'] is False
    assert 'D1A' in wrong.json()['details']['errors']['route_buttons']['missing']

    correct = _answer_from_spec(answer_payload['answer_spec'])
    submitted = client.post(f"/api/exam/shunting/questions/{first['id']}/submit", headers=student, json=correct)
    assert submitted.status_code == 200
    assert submitted.json()['all_correct'] is True
    assert submitted.json()['score'] == 1.0
