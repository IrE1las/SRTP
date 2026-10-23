"""Independent SDM station compiler. No teaching workbook or answer imports.

Route.txt supplies ordered route tokens; STADATA supplies equipment connections,
paired points, approach sections, clearances, signal controls and RJDelay.
Runtime rules reconstructed from these inputs are labelled in provenance.
"""
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path


def button_name(name, kind):
    if name in {'BA1', 'XDDZA', 'SFDZA'}:
        return name
    if name in {'XTA', 'XFTA', 'STA', 'SFTA'}:
        return name
    return name + ('LA' if kind == 'train' else 'DA')


def unique(items):
    return list(dict.fromkeys(items))


def section_name(name):
    """Two namespaces shipped in the SAME original application."""
    if name.startswith('DG'):
        return name[2:]+'DG'
    return {'GI':'IG', 'GII':'IIG', 'GIII':'IIIG', 'G4':'4G', 'G5':'5G',
            'WG1-19':'1/19WG', 'WG2-20':'2/20WG'}.get(name, name)


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
        mate = '' if mate == '0' else mate
        point = record['point']
        switches.append({'id': record['name'], 'name': record['name'], 'mate': mate,
                         'section': record['section'], 'x': point[0], 'y': point[1],
                         'geometry': record, 'source_row': record['offset'],
                         'throat': int(topology.get('Throat', '0'), 0)})
    signals = []
    for record in geometry:
        if record['type'] not in {0, 1}:
            continue
        fields = record['fields']
        signals.append({'id': record['name'], 'name': record['name'], 'type': 2 if record['type'] == 0 else 1,
                        'model': 3 if record['type'] == 0 else 1, 'x': fields[2], 'y': fields[3],
                        'geometry': record, 'source_row': record['offset'],
                        'entry': record['name'] in {'X', 'XF', 'XD', 'S', 'SF'},
                        'throat': int(data['topology'].get(record['name'], {}).get('Throat', '0'), 0),
                        'manual_unlock_seconds': int(data['topology'].get(record['name'], {}).get('RJDelay', '180'))})
    sections = []
    for name in unique([r['section'] for r in geometry if r['type'] == 2] +
                       [r['name'] for r in geometry if r['type'] in {3, 4}]):
        sections.append({'id': name, 'name': name,
                         'switches': [s['id'] for s in switches if s['section'] == name]})
    return compile_routes(data, switches, signals, sections, geometry)


def compile_routes(data, switches, signals, sections, geometry):
    topology = data['topology']
    switch_by_id = {s['id']:s for s in switches}
    section_names = {s['name'] for s in sections}
    signal_names = {s['name'] for s in signals}
    source_routes = data['routes']
    definitions = {}
    for index, raw in enumerate(source_routes, 1):
        definitions.setdefault((raw['kind'], raw['name'].rstrip(',')), []).append(index)

    def expand(index, visited=()):
        if index in visited:
            raise ValueError(f'子进路循环：{source_routes[index-1]["name"]}')
        raw = source_routes[index-1]
        demands, path, children, warnings = {}, [], [], []
        approach = None
        def point(sid, position):
            if sid not in switch_by_id:
                raise ValueError(f'未找到道岔：{sid}')
            if sid in demands and demands[sid] != position:
                raise ValueError(f'道岔 {sid} 同时要求定位和反位')
            demands[sid] = position
        for offset, token in enumerate(raw['tokens']):
            if token.startswith('#'):
                sid = token[1:].removesuffix('^')
                point(sid, int(token.endswith('^')))
                path.append(switch_by_id[sid]['section'])
            elif token.removeprefix('*') in section_names:
                name = token.removeprefix('*')
                if offset == 0 and token.startswith('*'):
                    approach = name
                else:
                    path.append(name)
            else:
                candidates = definitions.get((raw['kind'], token.rstrip(',')), [])
                if not candidates:
                    # Through routes refer to ordinary train segments.
                    raise ValueError(f'未找到子进路或区段：{token}')
                if len(candidates) != 1:
                    raise ValueError(f'子进路定义不唯一：{token}')
                child = expand(candidates[0], visited+(index,))
                if approach is None:
                    approach = child['approach']
                for sid, position in child['switches'].items():
                    point(sid, position)
                path.extend(child['sections'])
                children.append(f'SDM-{candidates[0]:03}')
                children.extend(child['children'])
                warnings.extend(child['warnings'])
        # ADD objects carry explicit flank-point demands on a selected
        # connection. Do not turn the protective point's section into a train
        # movement section; it is a separate locking requirement.
        explicit_count = len(demands)
        nodes = {'C'+sid for sid in demands} | set(raw['buttons'])
        for name, obj in topology.items():
            if 'AddPoint' not in obj:
                continue
            endpoints = [obj['ASide'], obj['BSide']]
            selected = all(node in nodes for node in endpoints)
            for node in endpoints:
                if node in topology and node.startswith('C') and node[1:] in demands:
                    point_obj = topology[node]
                    if point_obj.get('BSide') == name and demands[node[1:]] != 0:
                        selected = False
                    if point_obj.get('CSide') == name and demands[node[1:]] != 1:
                        selected = False
            if selected and obj.get('AddType') == '0':
                demand = int(obj['Demand'], 0)
                if demand not in {0x18, 0x81}:
                    raise ValueError(f'未知附加防护位置：{name}')
                point(obj['AddPoint'].removeprefix('C'), int(demand == 0x81))
        # Coupled point requirements are from this application's STADATA, never
        # inferred by comparing with the independent teaching station.
        for sid, position in list(demands.items()):
            mate = switch_by_id[sid]['mate']
            if mate:
                point(mate, position)
        return {'switches':demands, 'sections':unique(path), 'approach':approach, 'explicit_count':explicit_count,
                'children':unique(children), 'warnings':unique(warnings)}

    controls = data.get('topology_blocks', [])
    blocks = [{'id':name, 'signal':obj['Signal'],
               'type':'semi' if name.startswith('Semi') else 'auto',
               'reverse':obj.get('REVERSE') == '1'}
              for name,obj in topology.items() if name.startswith(('AutoBlock_', 'SemiBlock_'))]
    routes, button_defs = [], {}
    for index, raw in enumerate(source_routes, 1):
        kind = raw['kind']
        sequence = [button_name(name,kind) for name in raw['buttons']]
        for name, button in zip(raw['buttons'],sequence):
            actual = {'XDDZA':'XD','SFDZA':'SF','XTA':'X','XFTA':'XF','STA':'S','SFTA':'SF'}.get(name,name)
            button_defs[button] = {'id':button,'name':button, 'signal':actual if actual in signal_names else None,
                                   'type':4 if name=='BA1' else 2 if kind=='train' else 3}
        reasons = []
        try:
            parsed = expand(index)
        except ValueError as exc:
            reasons.append(str(exc))
            parsed = {'switches':{}, 'sections':[], 'approach':None, 'children':[], 'warnings':[]}
        start = {'XTA':'X','XFTA':'XF','STA':'S','SFTA':'SF'}.get(raw['buttons'][0],raw['buttons'][0])
        terminal = {'XDDZA':'XD','SFDZA':'SF'}.get(raw['buttons'][-1],raw['buttons'][-1])
        through = raw['buttons'][0].endswith('TA')
        departure = kind=='train' and terminal in {'X','XF','XD','S','SF'}
        if not parsed['sections']:
            reasons.append('未解析出进路内方区段')
        if start not in signal_names or terminal not in signal_names:
            reasons.append('始端或终端信号不存在')
        protection = []
        for name, obj in topology.items():
            if not name.endswith('FCX'):
                continue
            endpoints = [obj.get('ASide'),obj.get('BSide')]
            route_nodes = {'C'+sid for sid in parsed['switches']} | {start, terminal}
            # Only clearances on the actual selected point branches apply.
            on_path = all(node in route_nodes for node in endpoints)
            for node in endpoints:
                if node and node.startswith('C') and node[1:] in parsed['switches']:
                    point_obj = topology[node]
                    if point_obj.get('CSide')==name and parsed['switches'][node[1:]]!=1:
                        on_path=False
                    if point_obj.get('BSide')==name and parsed['switches'][node[1:]]!=0:
                        on_path=False
            if on_path:
                conditions = {obj[field].removeprefix('C'):1 for field in ['FstPoint','SecondPoint']
                              if obj.get(field,'0')!='0'}
                section = section_name(obj['EncroachSection'])
                if section not in parsed['sections']:
                    protection.append({'section':section,'clear_if_any':conditions,'source':name})
        # ZXJ_Control identifies straight receiving routes in the original file.
        straight = any(b['id'].startswith('ZXJ_Control_') and b['fields'].get('StartSignal')==start
                       and b['fields'].get('EndSignal')==terminal
                       and parsed.get('explicit_count')==int(b['fields']['PointNumber'],0) for b in controls)
        aspect = 'B' if kind=='shunt' else 'L' if departure or through else 'U' if straight else 'UU'
        segment_signals = [start]
        for child_id in parsed['children']:
            child = source_routes[int(child_id.split('-')[1])-1]
            if child['buttons'][0] in signal_names:
                segment_signals.append(child['buttons'][0])
        if through:
            segment_signals.extend(source_routes[int(cid.split('-')[1])-1]['buttons'][0] for cid in parsed['children'])
        routes.append({'id':f'SDM-{index:03}', 'name':raw['name'], 'kind':'train' if kind=='train' else 'long_shunt' if parsed['children'] else 'short_shunt',
                       'attribute':13 if through else 12 if departure else 11 if kind=='train' else 22 if parsed['children'] else 21,
                       'button_sequence':sequence, 'signal':start, 'terminal_signal':terminal,
                       'switches':parsed['switches'], 'sections':parsed['sections'],
                       'approach_section':parsed['approach'], 'overlap_sections':[], 'overlap_condition':None,
                       'clearance_checks':protection, 'hostile_signals':[], 'aspect':aspect,
                       'subroutes':parsed['children'], 'segment_signals':unique(segment_signals),
                       'block_signal': terminal if departure or through else None,
                       'source_sheet':'Route.txt','source_row':raw['line'],'source_raw':raw['raw'],
                       'condition_source':'original_application',
                       'warnings':parsed['warnings'], 'reasons':reasons,'status':'blocked' if reasons else 'ready'})
    sequences = Counter(tuple(r['button_sequence']) for r in routes)
    for route in routes:
        if sequences[tuple(route['button_sequence'])]>1:
            route['warnings'].append('原文件包含同按钮序列的多条定义；按可用条件、当前道岔位置和原行序选排，保留全部定义')
    counts = Counter(r['status'] for r in routes)
    return {'profile':'reference','station_name':'标准站',
            'source':'原应用 SDM/Route.txt + SWJDATA.dat + 联锁机/STADATA.TXT；独立于教学联锁表',
            'source_sha256':data['provenance']['sha256']['SWJDATA.dat'], 'provenance':data['provenance'],
            'signals':signals,'switches':switches,'sections':sections,
            'buttons':list(button_defs.values()),'switch_buttons':[],'labels':[],'boundaries':[],
            'reference_geometry':geometry,'routes':routes,'blocks':blocks,
            'capabilities':{'native_routes':True,'guide':True,'guide_total_lock':True,
                            'section_fault_unlock':True,'block_controls':'local_peer_simulation'},
            'counts':{'signals':len(signals),'switches':len(switches),'sections':len(sections),
                      'buttons':len(button_defs),'switch_buttons':0,'candidate_routes':len(routes),
                      'ready_routes':counts['ready'],'blocked_routes':counts['blocked'],'excluded_routes':0}}
