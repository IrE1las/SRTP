import copy
import json
from pathlib import Path

import pytest

from app.models.shunting_route import ShuntingDataset, ShuntingRoute
from app.services.shunting_data import import_reviewed_routes, validate_payload
from tests.helpers import auth_headers

PAYLOAD = Path(__file__).resolve().parents[3]/'ai_design/station/shunting_interlocking_reviewed.json'


@pytest.fixture
def payload():
    return json.loads(PAYLOAD.read_text(encoding='utf-8'))


def test_lossless_roundtrip_and_repeat_import_preserves_original_cells(db_session, payload):
    result = import_reviewed_routes(db_session, payload)
    db_session.commit()
    assert result['inserted'] == 35
    ids = []
    for source in payload['routes']:
        record = db_session.query(ShuntingRoute).filter_by(route_number=source['route_number']).one()
        assert record.fields == source['fields']
        assert record.rich_text == source['rich_text']
        assert record.provenance == source['provenance']
        ids.append(record.id)
    second = import_reviewed_routes(db_session, payload)
    db_session.commit()
    assert second == {'dataset_id':result['dataset_id'],'inserted':0,'updated':0,'total':35}
    assert [r.id for r in db_session.query(ShuntingRoute).order_by(ShuntingRoute.route_number)] == ids
    dataset = db_session.query(ShuntingDataset).one()
    assert [t['id'] for t in dataset.station_topology['tracks']] == ['5','III','I','II','4']
    assert dataset.source['reviewed'] is True


@pytest.mark.parametrize('defect', ['missing','duplicate','unreviewed','wrong_station','changed_text','unfixed_braces'])
def test_bad_payload_rejected_before_any_rows_written(db_session, payload, defect):
    bad = copy.deepcopy(payload)
    if defect == 'missing': bad['routes'].pop()
    if defect == 'duplicate': bad['routes'][1]['route_number'] = 20
    if defect == 'unreviewed': bad['source']['reviewed'] = False
    if defect == 'wrong_station': bad['station_key'] = 'DOWN_THROAT_STANDARD'
    if defect == 'changed_text': bad['routes'][0]['fields']['敌对信号'] = 'D7'
    if defect == 'unfixed_braces': bad['routes'][14]['fields']['道岔'] = '(17/19)、|23/25|、27'
    with pytest.raises(ValueError):
        import_reviewed_routes(db_session, bad)
    assert db_session.query(ShuntingDataset).count() == 0
    assert db_session.query(ShuntingRoute).count() == 0


def test_confirmed_literal_values_are_not_silently_repaired(payload):
    validate_payload(payload)
    rows = {r['route_number']:r['fields'] for r in payload['routes']}
    assert rows[32]['轨道区段'].endswith('<21>21DG IIIG')
    assert rows[44]['轨道区段'].startswith('25G、')
    assert rows[50]['敌对信号'].endswith('<1>D1')
    assert rows[54]['敌对信号'].endswith('<1/3>D1')
    assert rows[50]['轨道区段'].endswith('1/19WG')


def test_import_transaction_can_be_rolled_back(db_session, payload):
    import_reviewed_routes(db_session, payload)
    db_session.rollback()
    assert db_session.query(ShuntingDataset).count() == 0
    assert db_session.query(ShuntingRoute).count() == 0
