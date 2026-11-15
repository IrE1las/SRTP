"""Finite, source-backed teaching facts for the four classic exercises.

The model can arrange these facts, but cannot rewrite railway claims. CSV roles
are kept separate from traversed switches; all submitted values remain answers,
never route facts or instructions. The station files are the authority.
"""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

STATION_DIR = Path(__file__).resolve().parents[4] / 'ai_design' / 'station'
POSITION = {'normal': '定位', 'reverse': '反位'}
CATEGORY = {'route_buttons': '进路按钮', 'switches': '道岔', 'hostile_signals': '敌对信号', 'track_sections': '轨道区段'}
ERROR_TYPE = {'missing': '漏选', 'extra': '多选', 'wrong_position': '错位'}
PHOTO_SIGNAL = '原图预告信号'


class EvidenceError(ValueError):
    """Local sources cannot support a reliable explanation."""


def cells(value):
    return [s.strip() for s in re.split('[，、]', value) if s.strip()]


def load_evidence(route_type, correct):
    try:
        files = {name: (STATION_DIR / name).read_bytes() for name in (
            'interlocking_rules.md', 'station_topology.json', 'interlocking_table.csv', 'classic_exam_profiles.json')}
        if not files['interlocking_rules.md'].strip():
            raise EvidenceError('empty rules')
        topology = json.loads(files['station_topology.json'].decode('utf-8-sig'))
        profiles = json.loads(files['classic_exam_profiles.json'].decode('utf-8-sig'))
        if profiles['schema_version'] != 1 or profiles['reviewed_rules_sha256'] != hashlib.sha256(files['interlocking_rules.md']).hexdigest():
            raise EvidenceError('explanation templates require review against changed rules')
        profile = profiles['routes'][route_type]
        try:
            table_text = files['interlocking_table.csv'].decode('utf-8-sig')
        except UnicodeDecodeError:
            table_text = files['interlocking_table.csv'].decode('gb18030')
        row = next(r for r in csv.DictReader(io.StringIO(table_text)) if r['进路号码'] == profile['number'])
        roles, positions = {}, {}
        for token in cells(row['道岔']):
            code = re.search(r'\d+(?:/\d+)?', token).group()
            roles[code] = 'protective' if '[' in token else 'driven' if '{' in token else 'travel'
            positions[code] = 'reverse' if '(' in token else 'normal'
        conditional = {}
        for token in cells(row['轨道区段']):
            match = re.fullmatch(r'<(\(?\d+(?:/\d+)?\)?)>(.+)', token)
            if match:
                switch = match[1].strip('()')
                position = 'reverse' if '(' in match[1] else 'normal'
                if profile['conditions'].get(switch) != position or switch in roles:
                    raise EvidenceError('condition differs from table')
                conditional[match[2]] = switch
        expected = {
            'route_buttons': cells(row['排列进路按下按钮']), 'switches': positions,
            'hostile_signals': cells(row['敌对信号']),
            'track_sections': [re.sub(r'<[^>]+>', '', s) for s in cells(row['轨道区段'])],
        }
        for key, value in expected.items():
            if (value != correct[key] if isinstance(value, dict) else set(value) != set(correct[key])):
                raise EvidenceError('grading differs from table')
        sw_map = {s['id']: s for s in topology['switches']}
        track = profile['start_track']
        for step in profile['transitions']:
            code = step['switch']
            if (step['from'] != track or set(sw_map[code]['connects']) != {step['from'], step['to']}
                    or roles.get(code) != 'travel' or positions.get(code) != 'reverse'):
                raise EvidenceError('unsupported traversal')
            track = step['to']
        if track != profile['end_track']:
            raise EvidenceError('incorrect route destination')
        reverse_travel = {code for code, role in roles.items() if role == 'travel' and positions[code] == 'reverse'}
        if reverse_travel != {s['switch'] for s in profile['transitions']}:
            raise EvidenceError('missing traversal')
        if set(profile['conditions']) != set(conditional.values()):
            raise EvidenceError('unbound condition')
        signal_map = {s['name']: s for s in topology['signals']}
        track_map = {t['id']: t for t in topology['tracks']}
        if signal_map[correct['entry_signal']]['track'] != profile['start_track']:
            raise EvidenceError('entry track differs')
        if correct['direction'] == '接车' and track_map[profile['end_track']]['terminal_signal'] != correct['exit_signal']:
            raise EvidenceError('terminal differs')
        return {'topology': topology, 'profile': profile, 'roles': roles, 'positions': positions,
                'conditional': conditional, 'correct': correct, 'switches': sw_map, 'signals': signal_map,
                'tracks': track_map, 'sections': {s['name']: s for s in topology['sections']},
                'fingerprint': hashlib.sha256(b''.join(files.values())).hexdigest()}
    except (OSError, KeyError, StopIteration, UnicodeError, TypeError, AttributeError, ValueError) as exc:
        raise EvidenceError('station evidence unavailable or inconsistent') from exc


def validate_inventory(student, evidence):
    topology = evidence['topology']
    signals = evidence['signals']
    buttons = {s['name'] + s['button_suffix'] for s in signals.values()}
    buttons.update(t['terminal_signal'] + t['terminal_button_type'] for t in topology['tracks'])
    for side in topology['external_directions'].values():
        for direction in side.values():
            if direction.get('departure_terminal_button'):
                buttons.add(direction['departure_terminal_button'])
    hostiles = set(signals) | {s['name'] + 'D' for s in signals.values() if s['type'] == '出站'} | {PHOTO_SIGNAL}
    inventories = {'route_buttons': buttons, 'hostile_signals': hostiles,
                   'switches': set(evidence['switches']), 'track_sections': set(evidence['sections'])}
    if any(set(getattr(student, key)) - inventory for key, inventory in inventories.items()):
        raise ValueError('答案包含本站场之外的设备，请刷新页面后重新选择。')


def route_summary(evidence):
    profile, correct = evidence['profile'], evidence['correct']
    if correct['direction'] == '接车':
        start = f"列车由{correct['aspect']}经{correct['entry_signal']}进站信号进入{profile['start_track']}股道"
        finish = f"终到{profile['end_track']}股道。"
    else:
        start = f"列车从{profile['start_track']}股道出发"
        finish = f"沿{profile['end_track']}股道向{correct['aspect']}发车。"
    steps = [f"经{s['switch']}号道岔反位由{s['from']}股道转入{s['to']}股道" for s in profile['transitions']]
    return '，'.join([start, *steps, finish]) if steps else start + '，全程直向，' + finish


def _switch_reason(code, evidence):
    role, position = evidence['roles'][code], POSITION[evidence['positions'][code]]
    if role == 'protective':
        pair = next((pair for pair in evidence['topology']['cross_double_crossovers'] if code in pair), None)
        if not pair:
            raise EvidenceError('protective switch lacks crossing partner')
        other = next(s for s in pair if s != code)
        if evidence['roles'].get(other) != 'travel' or evidence['positions'].get(other) != 'reverse':
            raise EvidenceError('protective crossing partner is not traversed in reverse')
        short = f'{code}号道岔属于防护道岔，应锁闭在{position}，不属于列车实际经过的道岔。'
        detail = short + f'它与{other}号道岔组成交叉渡线；本进路经{other}反位换股道，须用{code}{position}防护交叉处。'
        return short, detail, '若未按要求防护，敌对进路可能侵入交叉处，造成侧向冲突。'
    if role == 'driven':
        mapping = evidence['topology']['switch_section_mapping']
        sw = evidence['switches'][code]
        own_sections = {mapping[p['id']] for p in [sw['switch_a'], sw.get('switch_b')] if p}
        peers = [(other, mapping[p['id']]) for other, other_sw in evidence['switches'].items()
                 if evidence['roles'].get(other) == 'travel' for p in [other_sw['switch_a'], other_sw.get('switch_b')]
                 if p and mapping[p['id']] in own_sections]
        if not peers:
            raise EvidenceError('driven switch lacks shared section')
        other, section = peers[0]
        short = f'{code}号道岔应带动到{position}，列车实际不经过它；它会随所在区段一起锁闭。'
        detail = short + f'它与本进路使用的{other}号道岔同处{section}区段，须在区段锁闭前置于{position}，避免被锁在妨碍平行作业的位置。'
        return short, detail, '若漏设或位置不对，它可能随区段锁在不利位置，妨碍其他平行进路的办理。'
    step = next((s for s in evidence['profile']['transitions'] if s['switch'] == code), None)
    if step:
        short = f"列车要经{code}号道岔由{step['from']}股道转入{step['to']}股道，必须使用反位。"
        return short, short + '锁闭在反位才能保持这条侧向走行路径，并防止列车通过时道岔被扳动。', '若位置不对，列车不能按规定换股道，进路走不通；若未锁闭，则不能保证通过时的位置。'
    short = f'{code}号道岔在本进路中按定位直向通过，应锁闭在定位。'
    return short, short + '本进路不在这组道岔处换股道，定位才能保持规定方向，并防止通过时被扳动。', '若置于反位，走行方向会偏离规定进路；若未锁闭，则不能保证列车通过时的位置。'


def _reason(category, code, kind, evidence):
    correct, profile = evidence['correct'], evidence['profile']
    if category == 'switches':
        if kind != 'extra':
            return _switch_reason(code, evidence)
        if code in profile['conditions']:
            targets = '、'.join(s for s, sw in evidence['conditional'].items() if sw == code)
            text = f'{code}号道岔是题设已知的{POSITION[profile["conditions"][code]]}条件，不在本题应填写的道岔列中。'
            return text, text + f'它影响{targets}区段的条件空闲检查；应保留题设条件，移除道岔答案中的多选项。', '多列会无谓限制平行作业；它的题设位置仍须用于判断条件区段，不能随答案的移除而改变。'
        text = f'{code}号道岔不属于本进路应填写的走行、防护或带动道岔。'
        return text, text + '请按本次进路的实际走行和道岔作用选择，不必把图上所有道岔都列入答案。', '多锁无关道岔会不必要地限制其他调车或接发车作业。'
    if category == 'route_buttons':
        begin, end = correct['route_buttons']
        if kind == 'extra':
            text = f'本进路应使用始端按钮{begin}和终端按钮{end}，{code}不是本题应选的按钮。'
        elif code == begin:
            text = f'{begin}是本进路的始端按钮，必须与终端按钮{end}共同确定这条进路。'
        elif correct['direction'] == '发车':
            text = f'{end}是{correct["aspect"]}的发车终端按钮，应与{begin}始端按钮配合。'
        else:
            track = evidence['tracks'][profile['end_track']]
            text = f'{end}是接车终端按钮，终端取{profile["end_track"]}股道的{track["terminal_signal"]}信号机，按钮类型按该股道的接车终端规定。'
            if not track['has_train_departure_signal']:
                text += '该股道虽只有调车终端信号，接车终端仍使用规定的列车按钮，不能照搬调车按钮。'
        return text, text + '始端和终端共同确定本题办理的进路。', '按钮漏选或选错，不能正确确定本题规定的进路始终端。'
    if category == 'track_sections':
        if kind == 'extra':
            section = evidence['sections'][code]
            if correct['direction'] == '发车' and section['type'] == 'G' and section['track'] == profile['start_track']:
                text = f'{code}是出发股道的站台区段，本题发车进路的区段检查集合不包含出发股道的这段。'
            else:
                text = f'{code}不属于本题应检查的走行区段，也不属于题设要求的条件区段。'
            return text, text + '请区分列车实际占用的区段、题设触发的条件区段和本次进路以外的区段。', '多加区段会把无关区段的占用作为本进路的限制，影响正常办理和平行作业。'
        if code in evidence['conditional']:
            sw = evidence['conditional'][code]
            position = POSITION[profile['conditions'][sw]]
            text = f'{code}是条件检查区段：题设规定{sw}号道岔{position}，该条件下须检查{code}空闲。'
            detail = text + f'本进路不实际经过{code}，但题设位置使其与本进路形成需检查的侵限连通关系；{sw}不因此变成本题道岔列中的走行道岔。'
            return text, detail, f'若漏查{code}空闲，将失去对相关侧向车辆侵入风险的检查，可能发生侧向冲突。'
        section = evidence['sections'][code]
        if correct['direction'] == '接车' and section['type'] == 'G':
            text = f'{code}是接车终到的{section["track"]}股道站台区段，列车将在此停车，必须检查空闲。'
        else:
            text = f'{code}处于本进路实际走行和占用的范围内，必须检查空闲并随进路锁闭。'
        return text, text + '只选道岔或信号不能替代轨道区段的空闲检查。', f'若漏查{code}，就不能排除进路内已有车辆占用，存在追尾或占用冲突风险。'
    # Hostile signals: distinguish a departure's shunting function from its main signal.
    if kind == 'extra':
        if code == PHOTO_SIGNAL:
            text = '原图预告信号不属于本题预设的敌对信号集合，不应仅因它出现在图中就列入敌对答案。'
        elif code == correct['entry_signal']:
            text = f'{code}是本进路的始端信号，不应把它本身列为需要封锁的敌对信号。'
        elif code.endswith('D') and code[:-1] in evidence['signals'] and code[:-1] in correct['hostile_signals']:
            text = f'本题接车终端应列{code[:-1]}信号本身，不能用其调车功能{code}代替。'
        elif correct['direction'] == '发车' and code + 'D' in correct['hostile_signals']:
            text = f'应限制的是始端信号的调车功能{code}D，不能将用于本次发车的{code}列为敌对。'
        elif code in evidence['signals'] and evidence['signals'][code]['track'] not in {profile['start_track'], *(s['to'] for s in profile['transitions'])}:
            signal_track = evidence['signals'][code]['track']
            traversed = '、'.join(dict.fromkeys([profile['start_track'], *(s['to'] for s in profile['transitions'])]))
            text = f'{code}在{signal_track}股道，本进路实际走行的股道为{traversed}，不经过它所在的股道；本题不把它列为敌对信号。'
        else:
            text = f'{code}不属于本题需要封锁的敌对信号，不能把图上全部信号都当成本进路的敌对信号。'
        return text, text + '应按本进路的走行范围、始终端作用及道岔锁闭后的冲突关系确定敌对信号。', '多列敌对信号会不必要地限制其他作业；若把本进路始端列入，还会与本次开放该信号的要求矛盾。' if code == correct['entry_signal'] else '多列敌对信号会不必要地限制本可平行办理的调车或接发车作业。'
    if correct['direction'] == '发车' and code == correct['entry_signal'] + 'D':
        text = f'{code}是始端{correct["entry_signal"]}出站信号的调车功能，其调车进路与本次发车进路直接冲突，必须封锁。'
        consequence = '漏封锁始端调车功能，调车作业可能与本次发车争用走行范围，发生进路冲突。'
    elif correct['direction'] == '接车' and code == correct['exit_signal']:
        text = f'{code}是接车终到{profile["end_track"]}股道的终端信号；接车占用该股道时，须防止相反方向发车或调车。'
        consequence = '若反方向发车或调车进路侵入已占用的终到股道，可能与接车发生迎面冲突。'
    else:
        signal = evidence['signals'][code]
        route_direction = 1 if correct['direction'] == '接车' else 2
        direction = '同向' if signal['direction'] == route_direction else '对向'
        text = f'{code}是本进路走行范围内{signal["track"]}股道上的{signal["type"]}信号，与本次列车走行{direction}，开放后其进路可能与本进路重叠。'
        consequence = '同向作业若侵入列车占用区段，可能发生追尾或挤岔冲突。' if direction == '同向' else '对向作业若侵入本进路，可能与列车发生迎面冲突。'
    return text, text + '需要把它列入敌对信号答案；选择相应轨道区段并不能替代敌对信号的封锁。', consequence


def build_cards(errors, student, evidence):
    cards = []
    for category in CATEGORY:
        for kind in ('missing', 'wrong_position', 'extra'):
            for value in errors[category].get(kind, []):
                code = value['switch'] if kind == 'wrong_position' else value
                short, detailed, consequence = _reason(category, code, kind, evidence)
                if category == 'switches' and kind != 'extra':
                    wanted = POSITION[evidence['positions'][code]]
                    diagnosis = f'{code}号道岔漏选，应为{wanted}。' if kind == 'missing' else f'{code}号道岔选成{POSITION[value["student"]]}，应为{wanted}。'
                    correction = f'将{code}号道岔加入答案并设置为{wanted}。'
                else:
                    diagnosis = f'{CATEGORY[category]}中{ERROR_TYPE[kind]}了{code}。'
                    correction = f'在{CATEGORY[category]}答案中' + (f'补选{code}。' if kind == 'missing' else f'移除{code}。')
                cards.append({'id': f'{category}:{kind}:{code}', 'category': category, 'code': code, 'error_type': kind,
                              'title': f'{ERROR_TYPE[kind]} · {code}', 'diagnosis': diagnosis, 'correction': correction,
                              'reasons': {'concise': short, 'detailed': detailed}, 'consequence': consequence})
    return cards
