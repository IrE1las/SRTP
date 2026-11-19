"""Adapt a stored station view without changing its recorded clicks or grades."""
from copy import deepcopy


def adapt_state(engine, data):
    data = deepcopy(data)
    state = data['session']
    aliases = engine.package['section_aliases']
    def expand(names):
        return list(dict.fromkeys(n for name in names for n in aliases.get(name, [name])))
    initial = engine.new_session(state['owner_id'], state['interval_available'])
    fresh = engine.sessions.pop(initial['session_id'])
    engine.reference_states.pop(initial['session_id'], None)
    old_sections = state['sections']
    state['sections'] = fresh.sections
    for name, value in old_sections.items():
        for current in expand([name]):
            if current in state['sections']:
                state['sections'][current].update(deepcopy(value))
    for sid, defaults in fresh.switches.items():
        state['switches'][sid] = {**defaults, **state['switches'].get(sid, {})}
    for instance in state['routes'].values():
        definition = engine.routes[instance['route_id']]
        old_path = list(instance['sections'])
        instance['sections'] = list(definition['sections'])
        instance['remaining'] = set(expand(instance['remaining'])) & set(instance['sections'])
        instance['protection_sections'] = expand(instance.get('protection_sections', []))
        instance['display_sections'] = [n for n in expand(instance.get('display_sections', [])) if n in instance['sections']]
        instance['release_due'] = {n:due for name,due in instance['release_due'].items()
                                   for n in expand([name]) if n in instance['sections']}
        instance['approach_section'] = definition['approach_section']
        if instance['progress'] >= 0:
            passed = expand(old_path[:instance['progress']+1])
            instance['progress'] = max((i for i,n in enumerate(instance['sections']) if n in passed), default=-1)
        instance.pop('segments', None)
        for segment in engine._segments(instance):
            signal = state['signals'][segment['signal']]
            segment['status'] = instance['status'] if instance['status'] in {'released','cancelled','setting','track_proving'} else (
                'signal_open' if signal.get('instance_id') == instance['id'] and signal.get('aspect') else 'closed_locked')
    data['runtime_profile'] = 'console-v1'
    return data
