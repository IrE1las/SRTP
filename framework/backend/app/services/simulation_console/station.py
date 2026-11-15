"""Read-only station package derived from the supplied data.xls workbook.

The workbook was exported without modifying it.  ``source_data.json`` retains
every source cell, sheet name, row number and the workbook SHA-256.  Business
decisions use IDs and explicit table fields; coordinates are only for drawing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re


SOURCE_PATH = Path(__file__).with_name("source_data.json")
CANDIDATE_ATTRIBUTES = {11, 12, 13, 14, 21, 22}
TRAIN_ATTRIBUTES = {11, 12, 13, 14}
SHUNT_ATTRIBUTES = {21, 22}
SWITCH_PATTERN = re.compile(r"(\d+)#([01])")


def _id(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    return [part for part in re.split(r"[,，、;；\s]+", str(value).strip()) if part and part != "NE"]


def _switches(value: object) -> tuple[dict[str, int], list[str]]:
    if value is None or not str(value).strip():
        return {}, []
    source = str(value)
    found = SWITCH_PATTERN.findall(source)
    residue = SWITCH_PATTERN.sub("", source)
    residue = re.sub(r"[,，、.;；\s]+", "", residue)
    errors = [f"道岔字段无法解析：{source}"] if residue else []
    result: dict[str, int] = {}
    for switch_id, position in found:
        if switch_id in result and result[switch_id] != int(position):
            errors.append(f"道岔 {switch_id} 同时要求定位和反位")
        result[switch_id] = int(position)
    return result, errors


def _rows(data: dict, sheet: str) -> list[dict]:
    table = data["sheets"][sheet]
    header = [str(value) if value is not None else f"column_{i}" for i, value in enumerate(table[0])]
    return [{**dict(zip(header, values)), "source_sheet": sheet, "source_row": index}
            for index, values in enumerate(table[1:], start=2)]


def _merge_unique(*groups: list[str]) -> list[str]:
    return list(dict.fromkeys(item for group in groups for item in group))


@lru_cache(maxsize=1)
def station_package() -> dict:
    data = json.loads(SOURCE_PATH.read_text(encoding="utf-8-sig"))
    signals = []
    for row in _rows(data, "信号机"):
        signals.append({
            "id": _id(row["SignalID"]), "name": row["Name"],
            "type": int(row["Type"]), "model": int(row["Model"]),
            "orientation": int(row["Orientation"]) if row["Orientation"] is not None else None,
            "protect_direction": int(row["ProtecDirect"]) if row["ProtecDirect"] is not None else None,
            "x": row["Pos_X"], "y": row["Pos_Y"],
            "inner_section": row["InnerSection"], "outer_section": row["OuterSection"],
            "source_row": row["source_row"],
        })
    sections = []
    for row in _rows(data, "区段"):
        sections.append({
            "id": _id(row["SectionID"]), "name": row["Name"], "type": int(row["Type"]),
            "x1": row["PStartX"], "y1": row["PStartY"], "x2": row["PEndX"], "y2": row["PEndY"],
            "label_x": row["NamePosX"], "label_y": row["NamePosY"],
            "switches": [_id(row[key]) for key in ("IncludeSw1", "IncludeSw2", "IncludeSw3") if row[key] is not None],
            "source_row": row["source_row"],
        })
    switches = []
    for row in _rows(data, "道岔"):
        switches.append({
            "id": _id(row["SwitchID"]), "name": _id(row["Name"]),
            "mate": _id(row["MatchSwID"]), "type": int(row["Type"]),
            "x": row["PCenterX"], "y": row["PCenterY"],
            "front_x": row["PFrontX"], "front_y": row["PFrontY"],
            "back_x": row["PBackStrX"], "back_y": row["PBackStrY"],
            "break_x": row["PBreakX"], "break_y": row["PBreakY"],
            "branch_x": row["PBackBentX"], "branch_y": row["PBackBentY"],
            "section": row["BlSection"], "source_row": row["source_row"],
        })
    boundaries = []
    for row in _rows(data, "区段边界"):
        boundaries.append({
            "shape": int(row["形状"]), "x": row["CX"], "y": row["CY"],
            "infringing": bool(row["是否侵线"]), "source_row": row["source_row"],
        })
    # Some raw section spans overlap at their shared insulated joint.  Keep
    # their original coordinates for audit, but stop each display stroke at
    # the explicit boundary so a free section cannot paint over a locked one.
    for section in sections:
        section["draw_x1"], section["draw_x2"] = section["x1"], section["x2"]
    display_dividers = []
    for first_index, first in enumerate(sections):
        for second in sections[first_index + 1:]:
            if first["y1"] != first["y2"] or second["y1"] != second["y2"] or first["y1"] != second["y1"]:
                continue
            overlap_start = max(first["x1"], second["x1"])
            overlap_end = min(first["x2"], second["x2"])
            if overlap_start >= overlap_end:
                continue
            joints = [joint for joint in boundaries if joint["y"] == first["y1"]
                      and overlap_start <= joint["x"] <= overlap_end]
            if len(joints) != 1:
                raise ValueError(f"区段 {first['name']}/{second['name']} 重叠区域缺少唯一绝缘节")
            left, right = sorted((first, second), key=lambda item: item["x1"])
            left["draw_x2"] = joints[0]["x"]
            right["draw_x1"] = joints[0]["x"]
            display_dividers.append({"left": left["name"], "right": right["name"],
                                     "x": joints[0]["x"], "y": joints[0]["y"]})
    for point in switches:
        point["draw_front_x"], point["draw_back_x"] = point["front_x"], point["back_x"]
        for divider in display_dividers:
            if point["y"] != divider["y"]:
                continue
            if point["section"] == divider["left"]:
                point["draw_front_x"] = min(point["draw_front_x"], divider["x"])
                point["draw_back_x"] = min(point["draw_back_x"], divider["x"])
            elif point["section"] == divider["right"]:
                point["draw_front_x"] = max(point["draw_front_x"], divider["x"])
                point["draw_back_x"] = max(point["draw_back_x"], divider["x"])
    labels = []
    for row in _rows(data, "车站名称"):
        labels.append({
            "text": row["文字名称"], "x": row["横坐标"], "y": row["纵坐标"],
            "size": row["字号"], "orientation": int(row["方向"]),
            "source_row": row["source_row"],
        })
    buttons = []
    for row in _rows(data, "按钮"):
        buttons.append({
            "id": _id(row["SiBtnID"]), "name": row["Name"], "type": int(row["Type"]),
            "signal": row["AssocSignal"], "x": row["iLockPosX"], "y": row["iLockPosY"],
            "source_row": row["source_row"],
        })
    switch_buttons = []
    for row in _rows(data, "道岔按钮"):
        switch_buttons.append({
            "name": row["名称"], "switch": _id(row["关联道岔"]),
            "x": row["道岔按钮坐标X"], "y": row["道岔按钮坐标Y"],
            "source_row": row["source_row"],
        })

    signal_names = {item["name"] for item in signals}
    signal_by_name = {item["name"]: item for item in signals}
    section_names = {item["name"] for item in sections}
    switch_by_id = {item["id"]: item for item in switches}
    button_by_name = {item["name"]: item for item in buttons}
    route_rows = _rows(data, "联锁表")
    routes: list[dict] = []
    route_by_id: dict[str, dict] = {}
    for row in route_rows:
        route_id = _id(row["编号"])
        attr = int(row["属性"])
        demands, syntax_errors = _switches(row["经过道岔（含防护和带动）"])
        buttons_sequence = _tokens(row["选排按钮"])
        route = {
            "id": route_id, "attribute": attr, "kind": (
                "train" if attr in TRAIN_ATTRIBUTES else "short_shunt" if attr == 21 else
                "long_shunt" if attr == 22 else "through"),
            "button_sequence": buttons_sequence, "source_button_sequence": row["选排按钮"],
            "signal": row["防护信号机"], "aspect": row["开放信号"],
            "terminal_signal": row["终端信号机"],
            "switches": demands, "sections": _tokens(row["包含区段"]),
            "overlap_sections": _tokens(row["超限区段"]),
            "overlap_condition": row["超限区段条件"],
            "hostile_signals": _tokens(row["敌对信号"]),
            "approach_section": row["接近区段"], "departure_section": row["离去区段"],
            "subroutes": _tokens(row["子进路"]),
            "source_sheet": "联锁表", "source_row": row["source_row"],
            "raw_values": row,
            "status": "excluded" if attr == 15 else "ready", "reasons": list(syntax_errors),
        }
        if route_id in route_by_id:
            route["reasons"].append(f"进路编号 {route_id} 重复")
        route_by_id[route_id] = route
        routes.append(route)

    sequence_counts = Counter(tuple(route["button_sequence"]) for route in routes if route["status"] == "ready")
    for route in routes:
        if route["status"] == "excluded":
            route["reasons"] = ["通过进路不在第一阶段执行范围"]
            continue
        if route["id"] == "209":
            route["reasons"].append("选排始端 D12A 与防护信号 D6 矛盾；待老师核对原始数据")
        if not route["button_sequence"]:
            route["reasons"].append("未配置完整按钮序列")
        if sequence_counts[tuple(route["button_sequence"])] > 1:
            route["reasons"].append("完整按钮序列与另一条进路重复，无法唯一识别")
        for name in route["button_sequence"]:
            if name not in button_by_name:
                route["reasons"].append(f"按钮 {name} 不在按钮表")
        if route["signal"] not in signal_names:
            route["reasons"].append(f"防护信号机 {route['signal']} 不在信号机表")
        elif route["button_sequence"]:
            first = button_by_name.get(route["button_sequence"][0])
            if first and first["signal"] != route["signal"]:
                route["reasons"].append("始端按钮关联信号与防护信号机不一致")
        if route["aspect"] not in {"U", "UU", "L", "B"}:
            route["reasons"].append(f"开放信号代码 {route['aspect']} 未定义")
        for section in route["sections"] + route["overlap_sections"]:
            if section not in section_names:
                route["reasons"].append(f"区段 {section} 不在区段表")
        for switch_id in route["switches"]:
            if switch_id not in switch_by_id:
                route["reasons"].append(f"道岔 {switch_id} 不在道岔表")
        if route["kind"] == "long_shunt" and not route["subroutes"]:
            route["reasons"].append("组合调车缺少子进路引用")
        if len(route["subroutes"]) != len(set(route["subroutes"])):
            route["reasons"].append("子进路重复引用")

    def expand(route: dict, ancestors: set[str] | None = None) -> tuple[list[str], dict[str, int], list[str]]:
        ancestors = ancestors or set()
        if route["id"] in ancestors:
            return [], {}, [f"子进路引用形成循环：{route['id']}"]
        sections_for_route = list(route["sections"])
        switches_for_route = dict(route["switches"])
        errors: list[str] = []
        for sub_id in route["subroutes"]:
            sub = route_by_id.get(sub_id)
            if sub is None:
                errors.append(f"子进路 {sub_id} 缺失")
                continue
            if sub["attribute"] != 21:
                errors.append(f"子进路 {sub_id} 不是短调车基本进路")
            sub_sections, sub_switches, sub_errors = expand(sub, ancestors | {route["id"]})
            sections_for_route = _merge_unique(sections_for_route, sub_sections)
            errors.extend(sub_errors)
            for switch_id, position in sub_switches.items():
                if switch_id in switches_for_route and switches_for_route[switch_id] != position:
                    errors.append(f"子进路道岔 {switch_id} 位置冲突")
                switches_for_route[switch_id] = position
        return sections_for_route, switches_for_route, errors

    for route in routes:
        if route["status"] == "excluded":
            continue
        sections_for_route, switches_for_route, errors = expand(route)
        route["sections"] = sections_for_route
        route["switches"] = switches_for_route
        route["reasons"].extend(errors)
        if not sections_for_route:
            route["reasons"].append("没有可核验的进路区段")
        for section in sections_for_route:
            if section not in section_names:
                route["reasons"].append(f"展开后区段 {section} 不在区段表")
        for switch_id in switches_for_route:
            if switch_id not in switch_by_id:
                route["reasons"].append(f"展开后道岔 {switch_id} 不在道岔表")
        if route["kind"] == "long_shunt" and route["subroutes"]:
            subroutes = [route_by_id[sub_id] for sub_id in route["subroutes"] if sub_id in route_by_id]
            if len(subroutes) == len(route["subroutes"]) and route["button_sequence"]:
                if (route["button_sequence"][0] != subroutes[0]["button_sequence"][0] or
                        route["button_sequence"][-1] != subroutes[-1]["button_sequence"][-1]):
                    route["reasons"].append("组合进路始端或终端与首末子进路不一致")
                for first, second in zip(subroutes, subroutes[1:]):
                    if not first["sections"] or not second["sections"] or not second["button_sequence"]:
                        continue
                    connecting_button = button_by_name.get(second["button_sequence"][0])
                    connecting_signal = signal_by_name.get(connecting_button["signal"]) if connecting_button else None
                    edge = {first["sections"][-1], second["sections"][0]}
                    signal_edge = ({connecting_signal["inner_section"], connecting_signal["outer_section"]}
                                   if connecting_signal else set())
                    if edge != signal_edge:
                        route["reasons"].append(
                            f"子进路 {first['id']}→{second['id']} 的边界区段与下一始端信号内外方不连续")
        # Both members of a double turnout must share a state and lock source.
        for switch_id, position in list(switches_for_route.items()):
            mate = switch_by_id.get(switch_id, {}).get("mate", "")
            if mate and mate != switch_id:
                if mate in switches_for_route and switches_for_route[mate] != position:
                    route["reasons"].append(f"双动道岔 {switch_id}/{mate} 位置要求冲突")
                elif mate in switch_by_id:
                    switches_for_route[mate] = position
        route["reasons"] = list(dict.fromkeys(route["reasons"]))
        if route["reasons"]:
            route["status"] = "blocked"
    counts = Counter(route["status"] for route in routes)
    return {
        "station_name": "联锁测试站", "source": data["source"], "source_sha256": data["sha256"],
        "signals": signals, "sections": sections, "switches": switches,
        "boundaries": boundaries, "labels": labels,
        "buttons": buttons, "switch_buttons": switch_buttons,
        "routes": routes,
        "counts": {"signals": len(signals), "switches": len(switches), "sections": len(sections),
                   "buttons": len(buttons), "switch_buttons": len(switch_buttons),
                   "candidate_routes": sum(route["attribute"] in CANDIDATE_ATTRIBUTES for route in routes),
                   "ready_routes": counts["ready"], "blocked_routes": counts["blocked"],
                   "excluded_routes": counts["excluded"]},
    }


def public_station_package() -> dict:
    """Public static data; omit full raw worksheet rows from the HTTP payload."""
    package = station_package()
    return {key: ([{k: v for k, v in route.items() if k != "raw_values"} for route in value]
                  if key == "routes" else value)
            for key, value in package.items()}
