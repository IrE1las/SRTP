"""Native SDM geometry + independently checked teaching interlocking conditions.

The two source stations share numbered equipment but use different names for
external sections. The explicit translation below never changes classic-exam
answers. Native routes without a unique, compatible checked row stay blocked.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

from .station import station_package

SECTION_NAMES = {
    'XNJG': 'YXDG',
    **{f'X{i}JG': 'YXG' for i in range(1, 4)},
    **{f'S{i}LQ': 'YXFG' for i in range(1, 4)},
    **{f'X{i}LQ': 'YSFG' for i in range(1, 4)},
    **{f'S{i}JG': 'YSG' for i in range(1, 4)},
}


def signal_name(name):
    return 'XD' if name == 'XN' else name


def button_name(name, kind):
    if name in {'BA1', 'XDDZA', 'SFDZA'}:
        return name
    return name + ('LA' if kind == 'train' else 'DA')


def checked_button(name, kind):
    if name == 'BA1':
        return 'BA'
    if name == 'XDDZA':
        return 'XNDA'
    if name == 'SFDZA':
        return 'SFDA'
    name = 'XN' if name == 'XD' else name
    return name + ('LA' if kind == 'train' else 'A' if re.fullmatch(r'D\d+', name) else 'DA')


def unique(items):
    return list(dict.fromkeys(items))


@lru_cache(maxsize=1)
def reference_station_package():
    data = json.loads(Path(__file__).with_name('reference_data.json').read_text(encoding='utf-8'))
    geometry = data['geometry']['records']
    switches = []
    for record in geometry:
        if record['type'] != 2:
            continue
        topology = data['topology'].get('C'+record['name'], {})
        mate = topology.get('CouplePoint', '').removeprefix('C')
        point, branches = record['point'], record['branches']
        switches.append({'id': record['name'], 'name': record['name'], 'mate': mate,
                         'section': record['section'], 'x': point[0], 'y': point[1],
                         'geometry': record, 'source_row': record['offset']})
    signals = []
    for record in geometry:
        if record['type'] not in {0, 1}:
            continue
        fields = record['fields']
        signals.append({'id': record['name'], 'name': record['name'], 'type': 2 if record['type'] == 0 else 1,
                        'model': 3 if record['type'] == 0 else 1, 'x': fields[2], 'y': fields[3],
                        'geometry': record, 'source_row': record['offset'],
                        'manual_unlock_seconds': int(data['topology'].get(record['name'], {}).get('RJDelay', '180'))})
    sections = []
    for name in unique([r['section'] for r in geometry if r['type'] == 2] +
                       [r['name'] for r in geometry if r['type'] in {3, 4}]):
        sections.append({'id': name, 'name': name,
                         'switches': [s['id'] for s in switches if s['section'] == name]})
    section_names = {s['name'] for s in sections}
    switch_by_id = {s['id']: s for s in switches}
    source_routes = data['routes']
    # A repeated definition is preserved in the audit, never silently overwritten.
    definitions = {}
    for route in source_routes:
        definitions.setdefault((route['kind'], route['name']), []).append(route)

    def expand(route, visited=()):
        identity = (route['kind'], route['name'])
        if identity in visited:
            return {}, [f'子进路循环：{route["name"]}']
        demands, errors = {}, []
        for token in route['tokens']:
            if token.startswith('#'):
                sid = token[1:].removesuffix('^')
                if sid not in switch_by_id:
                    errors.append(f'未找到道岔：{sid}')
                elif sid in demands and demands[sid] != int(token.endswith('^')):
                    errors.append(f'道岔 {sid} 位置冲突')
                else:
                    demands[sid] = int(token.endswith('^'))
            elif token.removeprefix('*') in section_names:
                continue
            else:
                candidates = definitions.get((route['kind'], token), [])
                if len(candidates) != 1:
                    errors.append(f'子进路或区段引用不唯一：{token}')
                    continue
                nested, issues = expand(candidates[0], visited+(identity,))
                errors.extend(issues)
                for sid, position in nested.items():
                    if sid in demands and demands[sid] != position:
                        errors.append(f'子进路道岔 {sid} 位置冲突')
                    demands[sid] = position
        return demands, errors

    checked = station_package()
    checked_sequences = {}
    for route in checked['routes']:
        checked_sequences.setdefault(tuple(route['button_sequence']), []).append(route)
    routes, button_defs = [], {}
    for index, raw in enumerate(source_routes, 1):
        kind = raw['kind']
        sequence = [button_name(name, kind) for name in raw['buttons']]
        for name, button in zip(raw['buttons'], sequence):
            actual_signal = name if name not in {'BA1', 'XDDZA', 'SFDZA'} else {'XDDZA': 'XD', 'SFDZA': 'SF'}.get(name)
            button_defs[button] = {'id': button, 'name': button, 'signal': actual_signal,
                                   'type': 4 if name == 'BA1' else 2 if kind == 'train' else 3}
        demands, reasons = expand(raw)
        candidates = checked_sequences.get(tuple(checked_button(name, kind) for name in raw['buttons']), [])
        base = deepcopy(candidates[0]) if len(candidates) == 1 else None
        if base:
            reasons.extend(base['reasons'])
            for sid, position in demands.items():
                if base['switches'].get(sid) != position:
                    reasons.append(f'软件进路与核对表的道岔 {sid} 要求不一致')
            for sid, position in base['switches'].items():
                if sid not in switch_by_id:
                    reasons.append(f'核对表引用不存在的道岔 {sid}')
            base['sections'] = unique(SECTION_NAMES.get(name, name) for name in base['sections'])
            base['overlap_sections'] = unique(SECTION_NAMES.get(name, name) for name in base['overlap_sections'])
            base['approach_section'] = SECTION_NAMES.get(base['approach_section'], base['approach_section'])
            base['hostile_signals'] = [signal_name(name.split('#')[0]) for name in base['hostile_signals']]
            for name in base['sections'] + base['overlap_sections']:
                if name not in section_names:
                    reasons.append(f'核对表引用未映射区段 {name}')
            checked_id = base['id']
        else:
            reasons.append('没有唯一对应的已核对联锁表记录，暂不开放该进路')
            checked_id = None
            base = {'attribute': 11 if kind == 'train' else 21, 'kind': 'train' if kind == 'train' else 'short_shunt',
                    'switches': demands, 'sections': [], 'overlap_sections': [], 'overlap_condition': None,
                    'approach_section': None, 'hostile_signals': [], 'aspect': None}
        base.update(id=f'SDM-{index:03}', name=raw['name'], button_sequence=sequence,
                    signal=raw['buttons'][0], terminal_signal=raw['buttons'][-1],
                    source_sheet='Route.txt', source_row=raw['line'], source_raw=raw['raw'],
                    checked_route_id=checked_id, subroutes=[], reasons=unique(reasons),
                    status='blocked' if reasons else 'ready')
        base.pop('raw_values', None)
        routes.append(base)
    duplicates = Counter(tuple(route['button_sequence']) for route in routes)
    for route in routes:
        if duplicates[tuple(route['button_sequence'])] > 1:
            route['status'] = 'blocked'
            route['reasons'].append('软件文件包含重复按钮序列，须核对后才能开放')
    counts = Counter(route['status'] for route in routes)
    return {'profile': 'reference', 'station_name': '标准站',
            'source': 'SDM/SWJDATA.dat + Route.txt；业务条件对照已核对的 data.xls',
            'source_sha256': data['provenance']['sha256']['SWJDATA.dat'],
            'signals': signals, 'switches': switches, 'sections': sections,
            'buttons': list(button_defs.values()), 'switch_buttons': [], 'labels': [], 'boundaries': [],
            'reference_geometry': geometry, 'routes': routes,
            'counts': {'signals': len(signals), 'switches': len(switches), 'sections': len(sections),
                       'buttons': len(button_defs), 'switch_buttons': 0, 'candidate_routes': len(routes),
                       'ready_routes': counts['ready'], 'blocked_routes': counts['blocked'], 'excluded_routes': 0}}
