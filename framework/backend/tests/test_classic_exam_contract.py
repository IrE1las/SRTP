"""Keep the graphical classic exercises aligned with the existing answer files."""
import csv
import re

import pytest

from app.api.interlocking_exam import CORRECT_ANSWERS, TABLE_FILE
from tests.test_exercise_api import auth_headers

ROUTES = [('dongjiao_to_III', '2'), ('dongjiao_to_I', '3'), ('dongjiao_to_4', '4'), ('beijing_depart_5', '9')]


def cells(value):
    return [part.strip() for part in re.split('[，、]', value) if part.strip()]


def file_answer(route_type, route_number):
    with TABLE_FILE.open(encoding='gb18030', newline='') as stream:
        row = next(r for r in csv.DictReader(stream) if r['进路号码'] == route_number)
    return {
        'route_type': route_type,
        'route_buttons': cells(row['排列进路按下按钮']),
        'switches': {re.search(r'\d+(?:/\d+)?', s).group(): 'reverse' if '(' in s else 'normal' for s in cells(row['道岔'])},
        'hostile_signals': cells(row['敌对信号']),
        'track_sections': [re.sub(r'<[^>]+>', '', s) for s in cells(row['轨道区段'])],
    }


@pytest.mark.parametrize('route_type,route_number', ROUTES)
def test_graphic_exam_matches_file_answers(client, route_type, route_number):
    payload = file_answer(route_type, route_number)
    answer = CORRECT_ANSWERS[route_type]
    for key in ['route_buttons', 'switches', 'hostile_signals', 'track_sections']:
        assert payload[key] == answer[key]
    headers = auth_headers(client, 'diagram_student', 'student')
    response = client.post('/api/exam/submit', headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()['all_correct']


@pytest.mark.parametrize('route_type,route_number', ROUTES)
def test_graphic_exam_diagnoses_independent_answer_categories(client, route_type, route_number):
    payload = file_answer(route_type, route_number)
    headers = auth_headers(client, 'diagram_errors', 'student')
    missing_button = payload['route_buttons'].pop()
    wrong_switch = next(iter(payload['switches']))
    payload['switches'][wrong_switch] = 'reverse' if payload['switches'][wrong_switch] == 'normal' else 'normal'
    extra_signal = next(s for s in ['D3', 'D15', 'SII'] if s not in payload['hostile_signals'])
    payload['hostile_signals'].append(extra_signal)
    missing_section = payload['track_sections'].pop()
    response = client.post('/api/exam/submit', headers=headers, json=payload).json()
    assert not response['all_correct']
    errors = response['details']['errors']
    assert missing_button in errors['route_buttons']['missing']
    assert wrong_switch in [s['switch'] for s in errors['switches']['wrong_position']]
    assert extra_signal in errors['hostile_signals']['extra']
    assert missing_section in errors['track_sections']['missing']


def test_given_switch_can_be_selected_and_judged_as_extra(client):
    payload = file_answer('beijing_depart_5', '9')
    payload['switches']['23/25'] = 'normal'
    headers = auth_headers(client, 'diagram_given', 'student')
    result = client.post('/api/exam/submit', headers=headers, json=payload).json()
    assert not result['all_correct']
    assert result['details']['errors']['switches']['extra'] == ['23/25']
