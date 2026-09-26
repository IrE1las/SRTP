"""Audit the *drawn* track geometry against the imported insulated joints."""

from __future__ import annotations

from .station import station_package


def _on_segment(point: tuple[float, float], edge: tuple, tolerance: float = 0.6) -> bool:
    (ax, ay), (bx, by), _ = edge
    px, py = point
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return False
    fraction = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - fraction * dx) ** 2 + (py - ay - fraction * dy) ** 2) ** 0.5 <= tolerance


def audit_geometry() -> dict:
    station = station_package()
    edges = []
    for section in station["sections"]:
        edges.append(((section["draw_x1"], section["y1"]),
                      (section["draw_x2"], section["y2"]), section["name"]))
    for point in station["switches"]:
        center = point["x"], point["y"]
        label = f"道岔 {point['id']}"
        edges.extend((center, other, label) for other in (
            (point["draw_front_x"], point["front_y"]),
            (point["draw_back_x"], point["back_y"]),
            (point["break_x"], point["break_y"]),
        ))
        edges.append(((point["break_x"], point["break_y"]),
                      (point["branch_x"], point["branch_y"]), label))
    open_ends = []
    for index, edge in enumerate(edges):
        for point in edge[:2]:
            if not any(index != other_index and _on_segment(point, other)
                       for other_index, other in enumerate(edges)):
                open_ends.append({"point": point, "element": edge[2]})
    unsupported_joints = [joint for joint in station["boundaries"]
                          if not any(_on_segment((joint["x"], joint["y"]), edge)
                                     for edge in edges)]
    return {"edge_count": len(edges), "open_ends": open_ends,
            "unsupported_joints": unsupported_joints}


if __name__ == "__main__":
    import json
    print(json.dumps(audit_geometry(), ensure_ascii=False, indent=2))
