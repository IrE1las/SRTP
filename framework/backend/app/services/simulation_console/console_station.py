"""Free-console circuit granularity, isolated from assessed station packages.

Device inputs and insulated DGs remain independent. Vehicle steps follow the
connected path and displays follow traversed branches. Mechanical coupling never
injects occupancy. Route tokens and flank demands come from the native data.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from .reference_station import compile_routes, reference_station_package, section_name, unique
from .console_paths import physical_path


@lru_cache(maxsize=1)
def console_station_package():
    original = deepcopy(reference_station_package())
    data = json.loads(Path(__file__).with_name('reference_data.json').read_text(encoding='utf-8'))
    switches = original['switches']
    aliases = {s['name']: [f'{sid}DG' for sid in s['switches']]
               for s in original['sections'] if len(s['switches']) > 1}
    for point in switches:
        point['source_section'] = point['section']
        point['section'] = f"{point['id']}DG"
        point['geometry']['section'] = point['section']
    sections = [{'id': p['section'], 'name': p['section'], 'switches': [p['id']]}
                for p in switches]
    sections += [s for s in original['sections'] if not s['switches']]
    # Retain source aliases while parsing explicit *DG tokens, then replace
    # them with the corresponding physical circuits in every compiled path.
    package = compile_routes(data, switches, original['signals'],
                             sections + [s for s in original['sections'] if s['name'] in aliases],
                             original['reference_geometry'])
    point_x = {p['section']: p['x'] for p in switches}
    shunt_signals = {s['name'] for s in package['signals'] if s['type'] == 2}
    for route in package['routes']:
        path = route['sections']
        expanded = []
        for i, name in enumerate(path):
            parts = aliases.get(name, [name])
            if len(parts) > 1:
                traversed = [n for n in path if n in parts]
                if traversed:
                    # #point tokens identify the ends actually traversed. A
                    # source group marker must not add the unused mate's DG.
                    expanded.extend(traversed)
                    continue
                # Source traversal order resolves the direction of explicit
                # combined-circuit tokens, including composite routes.
                previous = next((point_x[n] for n in reversed(expanded) if n in point_x), None)
                following = next((point_x[n] for n in path[i+1:] if n in point_x), None)
                if previous is not None:
                    parts = sorted(parts, key=lambda n: abs(point_x[n] - previous))
                elif following is not None:
                    parts = sorted(parts, key=lambda n: abs(point_x[n] - following), reverse=True)
                parts = parts[:1]
            expanded.extend(parts)
        route['sections'] = unique(expanded)
        approach = route['approach_section']
        route['approach_sections'] = list(aliases.get(approach, [approach] if approach else []))
        if approach in aliases:
            start = next(s for s in package['signals'] if s['name'] == route['signal'])
            route['approach_section'] = min(aliases[approach], key=lambda n: abs(point_x[n]-start['x']))
        route['clearance_checks'] = [{**check, 'section': name}
                                     for check in route['clearance_checks']
                                     for name in aliases.get(check['section'], [check['section']])]
        route['source_sections'] = list(route['sections'])
        route['sections'] = physical_path(route, switches, package['reference_geometry'], package['signals'])
        route['path_switches'] = {p['id']: route['switches'][p['id']] for p in switches
                                 if p['section'] in route['sections'] and p['id'] in route['switches']}
        # Insulation separates each displayed DG. Combined source labels and
        # mechanical coupling never merge two successive occupancy steps.
        route['movement_groups'] = [[section] for section in route['sections']]
        # A basic shunt can select either bounding signal of its terminal
        # non-point section (e.g. D1 -> D15, across 1/19WG). The native text
        # table also names the opposite-facing boundary (D1 -> D5).
        terminal = route['sections'][-1]
        route['terminal_aliases'] = [s['name']+'DA' for s in package['signals']
                                     if section_name(data['topology'].get(s['name'], {}).get('ApproachSection', '')) == terminal
                                     and s['name'] != route['signal']]
        if route['kind'] == 'train' or next(s for s in sections if s['name'] == terminal)['switches']:
            route['terminal_aliases'] = []
        route['button_sequence'] = [button[:-2]+'DA' if 0 < i < len(route['button_sequence'])-1
                                    and button.endswith('LA') and button[:-2] in shunt_signals else button
                                    for i, button in enumerate(route['button_sequence'])]
    used = {b for r in package['routes'] for b in r['button_sequence']}
    package['buttons'] = [b for b in package['buttons'] if b['name'] in used]
    package['counts']['buttons'] = len(package['buttons'])
    package.update(sections=sections, section_aliases=aliases, console_circuits=True)
    package['counts']['sections'] = len(sections)
    return package
