"""Pure, versioned scoring. No network, database writes or model calls."""
from copy import deepcopy
from app.services.operation_assessment.configuration import SPECIAL_COMMANDS, DEVICE_COMMANDS, RUBRIC_VERSION

ORDINARY_REJECTIONS = {'INVALID_SEQUENCE', 'SIGNAL_BUTTON_SEALED', 'SECTION_OCCUPIED', 'CLEARANCE_OCCUPIED',
    'SWITCH_ROUTE_LOCKED', 'SWITCH_MANUAL_LOCKED', 'SWITCH_SEALED', 'SWITCH_UNREPRESENTED',
    'SWITCH_POSITION_MISMATCH', 'HOSTILE_ROUTE', 'ROUTE_CONFLICT', 'BLOCK_NOT_PERMITTED',
    'INTERVAL_UNAVAILABLE', 'NO_FUNCTION_SELECTED', 'TARGET_TYPE_MISMATCH', 'ROUTE_NOT_LOCKED',
    'SWITCH_MOVING', 'UNLOCK_PENDING', 'APPROACH_LOCKED', 'SIGNAL_OPEN', 'GUIDE_TOTAL_LOCKED',
    'SIGNAL_ROUTE_LOCKED', 'SECTION_LOCKED', 'SEALED_FOR_ROUTE', 'SIGNAL_UNLIT'}
IGNORE_REJECTIONS = {'INVALID_PIN'}


def review(reason):
    return {'status': 'needs_review', 'suggested_score': None, 'reason': reason,
            'rubric_version': RUBRIC_VERSION, 'items': [], 'episodes': []}


def score(config, transitions, final_state):
    targets = set(config['route_ids'])
    definitions = {r['id']: r for r in config['routes']}
    prefixes = [r['button_sequence'] for r in config['routes']]
    device_scope = {name for r in config['routes'] for name in [*r['switches'], *r['sections'], *r['segment_signals']]}
    current = {'routes': {}, 'switches': {}, 'sections': {}, 'signals': {}, 'selected': []}
    milestones = {'A1': False, 'A2': False, 'A3': False, 'A4': False}
    instances = {}
    episodes = []
    unknown = []
    special_chain = None
    device_active = {}

    def add(code, points, seq, message, key=None, recovered=None):
        if key:
            old = next((e for e in episodes if e.get('key') == key), None)
            if old:
                if points > old['points'] and seq not in old['evidence']:
                    old['evidence'].append(seq)
                if points > old['points']:
                    old.update(code=code, points=points, message=message)
                if recovered is not None:
                    old['recovered'] = recovered
                return
        episodes.append({'code': code, 'dimension': 'B' if code.startswith('B') else 'C', 'points': points,
                         'message': message, 'evidence': [seq], 'key': key,
                         'recovered': recovered if recovered is not None else False})

    def locked(r):
        iid = r['id']
        sections = r['sections'] + r.get('protection_sections', [])
        def owners(value):
            return value.get('__runtime_set__', []) if isinstance(value, dict) else value
        return all(iid in owners(current['sections'].get(n, {}).get('owners', [])) for n in sections) and all(
            iid in owners(current['switches'].get(n, {}).get('owners', [])) for n in r['switches'])

    def opened(r):
        definition = definitions.get(r['route_id'])
        return bool(definition and r.get('mode') == 'normal' and r['status'] == 'signal_open' and all(
            current['signals'].get(n, {}).get('instance_id') == r['id'] and
            current['signals'][n].get('aspect') == definition['aspect'] for n in definition['segment_signals']))

    for transition in transitions:
        seq, value = transition['sequence'], transition['content']
        before_selected = list(current['selected'])
        source = value.get('source') or {}
        delta = value.get('delta', {})
        before_devices = {(key,name): deepcopy(current[key].get(name)) for key in ('switches','signals') for name in delta.get(key,{})}
        for key in ('routes', 'switches', 'sections', 'signals'):
            current[key].update(deepcopy(delta.get(key, {})))
        if 'selected' in delta:
            current['selected'] = delta['selected']
        request = source.get('request_routes', [])
        if targets.intersection(request) and source.get('mode') == 'normal':
            milestones['A1'] = True
        result = source.get('result', {})
        function = source.get('button_id') if source.get('is_command') else None
        code = result.get('reason_code')
        if source and source.get('action') == 'button' and not source.get('is_command'):
            special_chain = None
        # Source events are not model-generated classifications.
        if function in SPECIAL_COMMANDS and code not in IGNORE_REJECTIONS:
            command_key = str(source.get('target_id')) + ':' + function
            if not special_chain or special_chain[0] != command_key:
                special_chain = (command_key, 'special:' + str(seq))
            add('B05' if result.get('accepted') else 'B04', 30 if result.get('accepted') else 10,
                seq, '使用了本正常接车题不允许的特殊处理', key=special_chain[1])
        elif function in DEVICE_COMMANDS and result.get('accepted') and set(str(source.get('target_id')).split('/')).intersection(device_scope) and any(delta.get(k) for k in ('switches', 'signals')):
            field = 'manual_locked' if 'SINGLE_' in function else ('sealed' if 'SEAL' in function else 'lit')
            key = (field, tuple(sorted(before_devices)))
            active = device_active.get(key)
            if active and all(current[c['collection']].get(c['device'],{}).get(field,field=='lit')==c['values'][field]
                              for c in active['restore_checks']):
                active['recovered'] = True
                active['evidence'].append(seq)
                del device_active[key]
            elif not active:
                add('B03', 5, seq, '对题目不要求改变的设备进行了实际操作')
                episodes[-1]['restore_checks'] = [{'collection': k, 'device': n,
                    'values': {field:(v or {}).get(field,field=='lit')}} for (k,n),v in before_devices.items()]
                device_active[key] = episodes[-1]
        elif result.get('accepted') is False and code not in IGNORE_REJECTIONS:
            if code in ORDINARY_REJECTIONS:
                related = next((iid for iid,r in current['routes'].items() if r['route_id'] not in targets and
                    r['status'] not in {'cancelled','released'} and code in {'HOSTILE_ROUTE','SIGNAL_ROUTE_LOCKED','SECTION_LOCKED','SWITCH_ROUTE_LOCKED'} and
                    set(result.get('devices',[])).intersection({r['signal'],*r['sections'],*r['switches']})),None)
                if related:
                    old = next((e for e in episodes if e.get('key')==related),None)
                    if old and seq not in old['evidence']:
                        old['evidence'].append(seq)
                else:
                    add('C02', 5, seq, '一次普通无效操作被拒绝')
            else:
                unknown.append({'sequence': seq, 'reason_code': code})
        if source.get('button_id') == 'CLEAR_SELECTION' and before_selected and not any(
                path[:len(before_selected)] == before_selected for path in prefixes):
            add('C01', 2, seq, '临时选择偏离目标，已在形成进路前清除', recovered=True)
        for event in value.get('events', []):
            if event['kind'] == 'selection_timeout' and before_selected:
                add('C03', 2, seq, '临时按钮选择超时，已清除', recovered=True)
            iid = event.get('instance_id')
            route = current['routes'].get(iid)
            if event['kind'] == 'route_cancel_complete' and route:
                if route['route_id'] in targets and instances.get(iid, {}).get('opened'):
                    add('C04', 2, seq, '目标曾完成，之后进行了题目未要求的取消')
                old = next((e for e in episodes if e.get('key') == iid), None)
                if old:
                    old['recovered'] = True
                    old['evidence'].append(seq)
        for iid, route in current['routes'].items():
            record = instances.setdefault(iid, {'locked': False, 'opened': False})
            if route['route_id'] in targets and route.get('mode') == 'normal':
                if locked(route):
                    record['locked'] = True
                    milestones['A2'] = True
                if record['locked'] and opened(route):
                    record['opened'] = True
                    milestones['A3'] = True
            elif route['status'] not in {'released', 'cancelled'}:
                # Any wrong route with resources reserved has already had a business effect.
                if locked(route):
                    any_open = any(s.get('instance_id') == iid and s.get('aspect') is not None for s in current['signals'].values())
                    add('B02' if any_open else 'B01', 20 if any_open else 10, seq,
                        '错误进路的信号已开放' if any_open else '错误进路已形成实际锁闭', key=iid)

    # The seal must match the replayed transition state; do not invent missing facts.
    for key in ('routes', 'switches', 'sections', 'signals'):
        if current[key] != final_state.get(key, {}):
            return review('业务事件差量与截止状态不一致')
    if unknown:
        return {**review('存在尚未核验的拒绝原因，请人工核对'), 'unclassified': unknown}
    active_wrong = any(r['route_id'] not in targets and r['status'] not in {'cancelled', 'released'} for r in current['routes'].values())
    milestones['A4'] = milestones['A3'] and not active_wrong and any(
        r['route_id'] in targets and locked(r) and opened(r) and not r.get('cancel_pending') for r in current['routes'].values())
    for item in episodes:
        if item['code'] in {'C02','C04'}:
            item['recovered'] = bool(milestones['A4'])
        if item['code']=='B03':
            checks=item.pop('restore_checks',[])
            item['recovered'] = item['recovered'] or bool(checks) and all(all(current[c['collection']].get(c['device'],{}).get(k,k=='lit')==v
                for k,v in c['values'].items()) for c in checks)
    if milestones['A2'] and not milestones['A1']:
        return review('缺少目标办理请求的关联证据')
    a = sum(points for key, points in [('A1', 10), ('A2', 20), ('A3', 20), ('A4', 10)] if milestones[key])
    b = max(0, 30 - sum(e['points'] for e in episodes if e['dimension'] == 'B')) if milestones['A1'] else 0
    c = max(0, 10 - sum(e['points'] for e in episodes if e['dimension'] == 'C')) if milestones['A1'] else 0
    cap = 100 if milestones['A4'] else 59
    cap_reasons = [] if milestones['A4'] else ['截止时核心目标未完成或未保持']
    if config.get('wrong_signal_cap') and any(e['code'] == 'B02' for e in episodes):
        cap = min(cap, 59)
        cap_reasons.append('本场已确认将错误信号开放列为关键操作不合格')
    return {'status': 'ready', 'rubric_version': RUBRIC_VERSION, 'milestones': milestones,
            'dimensions': {'task': a, 'procedure': b, 'fluency': c}, 'raw_score': a + b + c,
            'cap': cap, 'cap_reasons': cap_reasons, 'suggested_score': min(a + b + c, cap),
            'episodes': episodes, 'items': [dict(code=k, earned=v, points=p) for (k, v), p in zip(milestones.items(), [10, 20, 20, 10])]}
