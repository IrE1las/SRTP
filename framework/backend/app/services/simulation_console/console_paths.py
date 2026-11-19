"""Trace the chosen rail branches; source group names do not define direction.

Each switch branch joins only at its explicit geometry endpoints. Crossing
polylines never create a junction, and unused coupled ends remain flank demands.
"""
from collections import defaultdict


def physical_path(route, switches, geometry, signals):
    points = {p['section']: p for p in switches}
    tracks = {r['name']: r for r in geometry if r['type'] in (3, 4)}
    graph = defaultdict(list)
    edges = []

    def add(section, vertices):
        a, b = tuple(vertices[0]), tuple(vertices[-1])
        index = len(edges)
        edges.append((section, a, b))
        graph[a].append(index)
        graph[b].append(index)

    for name in route['sections']:
        if name in tracks:
            add(name, tracks[name]['points'])
        else:
            point = points[name]
            for branch in (0, 2 if route['switches'][point['id']] else 1):
                add(name, [point['geometry']['point'], *point['geometry']['branches'][branch]])
    ends = [node for node, links in graph.items() if len(links) == 1]
    if not ends:
        raise ValueError(f"{route['id']} 未找到行车路径端点")
    signal = next(s for s in signals if s['name'] == route['signal'])
    node = min(ends, key=lambda n: (n[0]-signal['x'])**2+(n[1]-signal['y'])**2)
    # All recovered station signal anchors are directly above/below the rail
    # endpoint. Fail visibly if new data cannot establish the start unambiguously.
    if node[0] != signal['x'] or abs(node[1]-signal['y']) > 30:
        raise ValueError(f"{route['id']} 始端信号与行车路径不接续")
    ordered, seen = [], set()
    while True:
        links = [index for index in graph[node] if index not in seen]
        if not links:
            return ordered
        if len(links) != 1:
            raise ValueError(f"{route['id']} 选定支路存在未消解的分叉")
        index = links[0]
        seen.add(index)
        name, a, b = edges[index]
        if name not in ordered:
            ordered.append(name)
        node = b if node == a else a
