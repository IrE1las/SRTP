from copy import deepcopy
from app.models.operation_assessment import OperationAssessmentConfig
from app.services.operation_assessment.evidence import digest, engine_version

RUBRIC_VERSION = 'reception-1.0'
SPECIAL_COMMANDS = {'MANUAL_UNLOCK_ROUTE', 'SECTION_FAULT_UNLOCK', 'GUIDE_ARM', 'GUIDE_MAINTAIN',
                    'GUIDE_TOTAL_LOCK', 'GUIDE_TOTAL_UNLOCK', 'BLOCK_ACCIDENT_RESET', 'BLOCK_TOTAL_AUX',
                    'BLOCK_DEPARTURE_AUX', 'BLOCK_RECEPTION_AUX'}
DEVICE_COMMANDS = {'SWITCH_SINGLE_LOCK', 'SWITCH_SINGLE_UNLOCK', 'SWITCH_SEAL', 'SWITCH_UNSEAL',
                   'SIGNAL_SEAL', 'SIGNAL_UNSEAL', 'SIGNAL_LIGHT_ON', 'SIGNAL_LIGHT_OFF'}


def view(db, version_id):
    row = db.get(OperationAssessmentConfig, version_id)
    return {'revision': row.revision if row else 0, **deepcopy(row.content if row else {
        'enabled': False, 'route_ids': [], 'wrong_signal_cap': False, 'confirmed': False})}


def save(db, user, qid, body):
    from app.services import operations as ops
    q = ops.question(db, user, qid)
    version = ops.latest(db, qid)
    if version.status != 'draft' or q.disabled:
        ops.fail('请先建立可编辑的题目草稿；已发布的评分配置不能修改')
    row = db.get(OperationAssessmentConfig, version.id)
    if body.revision != (row.revision if row else 0):
        ops.fail('评价配置已修改，请刷新后核对')
    values = body.model_dump(exclude={'revision'})
    values['route_ids'] = list(dict.fromkeys(values['route_ids']))
    routes = {r['id']: r for r in ops.reference_station_package()['routes']}
    if values['enabled']:
        if not values['confirmed'] or not values['route_ids']:
            ops.fail('请选择接车进路并确认评分标准', 422)
        chosen = [routes.get(rid) for rid in values['route_ids']]
        entries = {s['name'] for s in ops.reference_station_package()['signals'] if s.get('entry')}
        if any(not r or r['kind'] != 'train' or r['signal'] not in entries or r.get('subroutes') for r in chosen):
            ops.fail('首期仅支持本站进站信号始端的单条正常列车接车进路', 422)
        if len({(r['signal'], r['button_sequence'][-1], r['aspect']) for r in chosen}) != 1:
            ops.fail('认可的替代进路必须具有相同始端、终端和规定信号显示', 422)
    values.update(rubric_version=RUBRIC_VERSION, schema_version=1)
    if row:
        row.revision += 1
        row.content = values
    else:
        db.add(OperationAssessmentConfig(version_id=version.id, revision=1, content=values))
    db.commit()
    return view(db, version.id)


def freeze(db, version, initial):
    from app.services import operations as ops
    from app.services.simulation_console.reference_runtime import ReferenceSimulationService
    from app.services.simulation_console import clock
    from app.services.operation_assessment import evidence
    config = view(db, version.id)
    if not config['enabled']:
        return None
    routes = {r['id']: r for r in ops.reference_station_package()['routes']}
    config['routes'] = [deepcopy(routes[rid]) for rid in config['route_ids']]
    config['engine_version'] = engine_version()
    config['station_version'] = version.station_version
    # A mismatch between the explicit target and the teacher's demonstration must be visible.
    recorded = [e['button_id'] for e in (version.standard_log or []) if e['action']=='button']
    if not any(recorded == r['button_sequence'] for r in config['routes']) or any(
        not e['result']['accepted'] or e['action'] not in {'button','cancel_selection'} for e in (version.standard_log or [])):
        ops.fail('此接车模板的标准示范应为目标进路的一次完整无误办理，请核对目标或重新录制')
    # Independently check that every declared variant can complete from this initial state.
    for route in config['routes']:
        engine = ReferenceSimulationService(ops.reference_station_package())
        snap = engine.new_session(0, initial.get('interval_available', True), initial.get('occupied_sections', []))
        session = engine.sessions[snap['session_id']]
        for button in route['button_sequence']:
            result = engine.select_button(session.id, 0, button)
            if not result['accepted']:
                ops.fail('当前初始条件下目标进路无法完成，请检查题设和评价配置')
        # Advance a disposable in-memory engine at its scheduled instants, without database writes.
        start = clock.time()
        for _ in range(100):
            if any(r['route_id'] in config['route_ids'] and r['status'] == 'signal_open' for r in session.routes.values()):
                break
            due = evidence.due_times(engine, session)
            if not due:
                ops.fail('目标进路示范未能达到信号开放状态')
            offset = clock.time() - clock.monotonic()
            instant = min(due) + offset
            if instant > start + 60:
                ops.fail('目标进路无法在正常预演范围内完成')
            with clock.at(instant):
                engine.snapshot(session.id, 0)
        else:
            ops.fail('目标进路预演未完成')
    config['fingerprint'] = digest(config)
    return config
