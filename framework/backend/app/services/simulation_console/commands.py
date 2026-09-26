"""Commands shared by free simulation and durable experiment attempts.

Operate on the existing RuntimeSession, using the same route guard/arranger.
The caller owns authorization, optimistic concurrency and persistence.
"""
from copy import deepcopy
from time import monotonic, time

from .runtime import RuntimeSession


def dump_session(session):
    def encode(value):
        if isinstance(value, set):
            return sorted(value)
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [encode(v) for v in value]
        return value
    data = {k: encode(v) for k, v in vars(session).items() if k not in {"mutex", "history", "selection_deadline"}}
    data["selection_expires_at"] = time() + session.selection_deadline - monotonic() if session.selection_deadline else None
    # Persist wall-clock deadlines, never process-local monotonic values.
    for route in data["routes"].values():
        route["release_due"] = {k: time() + v - monotonic() for k, v in route["release_due"].items()}
    return data


def load_session(data):
    data = deepcopy(data)
    deadline = data.pop("selection_expires_at", None)
    session = RuntimeSession(**data)
    session.selection_deadline = monotonic() + deadline - time() if deadline else None
    for state in [*session.sections.values(), *session.switches.values()]:
        state["owners"] = set(state["owners"])
    for route in session.routes.values():
        route["remaining"] = set(route["remaining"])
        route["release_due"] = {k: monotonic() + v - time() for k, v in route["release_due"].items()}
    return session


def group_ids(service, target):
    ids = target.split("/")
    if not ids or any(sid not in service.switch_defs for sid in ids):
        return []
    group = {ids[0]}
    mate = service.switch_defs[ids[0]]["mate"]
    if mate in service.switch_defs:
        group.add(mate)
    return sorted(group, key=int) if set(ids).issubset(group) else []


def reevaluate_signals(service, session):
    for route in session.routes.values():
        if route["status"] in {"released", "cancelled"}:
            continue
        definition = service.routes[route["route_id"]]
        fact = service._blocking_fact(session, definition, route["id"])
        if fact and session.signals[route["signal"]]["aspect"] is not None:
            session.signals[route["signal"]].update(aspect=None, close_reason=fact[0])
            route["status"] = "closed_locked"
            service._event(session, "signal_close", f"{route['signal']} 信号关闭；{fact[1]}，保留锁闭", route["route_id"])


def execute(service, session, command):
    kind, target = command["type"], command.get("target", "")
    payload = command.get("payload", {})
    service.sessions[session.id] = session
    before = service._snapshot(session)
    start = session.version
    def reject(code, message, devices=None):
        return service._reject(session, message, reason_code=code, devices=devices or [target])
    def success(message):
        service._event(session, kind, message)
        return {"accepted": True, "reason_code": "OK", "message": message, "snapshot": service._snapshot(session)}

    if kind == "PRESS_BUTTON":
        # Capture the submitted sequence before the arranger clears its buffer.
        sequence = ([] if session.selection_deadline and monotonic() >= session.selection_deadline else list(session.selected)) + [target]
        result = service.select_button(session.id, session.owner_id, target)
        result["button_sequence"] = sequence
    elif kind == "CLEAR_SELECTION":
        result = service.clear_selection(session.id, session.owner_id)
    elif kind.startswith("SWITCH_") or kind in {"SET_SWITCH_INDICATION", "RESTORE_SWITCH_INDICATION"}:
        ids = group_ids(service, target)
        if not ids:
            result = reject("UNKNOWN_DEVICE", "道岔组不存在")
        else:
            states = [session.switches[sid] for sid in ids]
            sections = [service.switch_defs[sid]["section"] for sid in ids]
            occupied = [name for name in sections if session.sections.get(name, {}).get("occupied")]
            if kind in {"SWITCH_TOTAL_NORMAL", "SWITCH_TOTAL_REVERSE"}:
                if occupied:
                    result = reject("SECTION_OCCUPIED", f"{'、'.join(occupied)} 占用，整组道岔不能转换", occupied)
                elif any(not s["represented"] for s in states):
                    result = reject("SWITCH_UNREPRESENTED", "道岔组无表示，不能转换", ids)
                elif any(s["manual_locked"] for s in states):
                    result = reject("SWITCH_MANUAL_LOCKED", "道岔组已单锁，不能转换", ids)
                elif any(s["owners"] for s in states):
                    result = reject("SWITCH_ROUTE_LOCKED", "道岔组已被进路锁闭，不能转换", ids)
                else:
                    for s in states:
                        s["position"] = int(kind == "SWITCH_TOTAL_REVERSE")
                    result = success(f"{'/'.join(ids)} 道岔组已转至{'反位' if states[0]['position'] else '定位'}，表示正常")
            else:
                updates = {"SWITCH_SINGLE_LOCK": ("manual_locked", True), "SWITCH_SINGLE_UNLOCK": ("manual_locked", False),
                           "SWITCH_SEAL": ("sealed", True), "SWITCH_UNSEAL": ("sealed", False),
                           "SET_SWITCH_INDICATION": ("represented", False), "RESTORE_SWITCH_INDICATION": ("represented", True)}
                if kind not in updates:
                    result = reject("UNKNOWN_COMMAND", "不支持此命令")
                else:
                    field, value = updates[kind]
                    for s in states:
                        s[field] = value
                    labels = {"SWITCH_SINGLE_LOCK": "单锁", "SWITCH_SINGLE_UNLOCK": "单解", "SWITCH_SEAL": "封闭",
                              "SWITCH_UNSEAL": "解除封闭", "SET_SWITCH_INDICATION": "设置失表示", "RESTORE_SWITCH_INDICATION": "恢复表示"}
                    result = success(f"{'/'.join(ids)} 道岔组：{labels[kind]}")
                    reevaluate_signals(service, session)
    elif kind in {"SET_SECTION_OCCUPANCY", "CLEAR_SECTION_OCCUPANCY"}:
        occupancy = "clear" if kind == "CLEAR_SECTION_OCCUPANCY" else payload.get("kind")
        if target not in session.sections:
            result = reject("UNKNOWN_DEVICE", "区段不存在")
        elif occupancy not in {"vehicle", "fault", "clear"}:
            result = reject("INVALID_OCCUPANCY", "占用类型无效")
        else:
            session.sections[target].update(occupied=occupancy != "clear", occupancy_kind=occupancy, occupancy_origin="student_command")
            result = success(f"{target} 区段：{ {'clear': '恢复空闲', 'vehicle': '车列占用', 'fault': '故障占用'}[occupancy] }")
            reevaluate_signals(service, session)
    elif kind in {"CANCEL_ROUTE", "REPEAT_OPEN_SIGNAL"}:
        route = session.routes.get(target)
        if not route or route["status"] in {"released", "cancelled"}:
            result = reject("ROUTE_NOT_LOCKED", "请选择仍锁闭的原进路")
        elif route.get("train_started") or (route["approach_section"] and session.sections[route["approach_section"]]["occupied"]):
            result = reject("APPROACH_LOCKED", "已接近或已行车，不能执行本期的总取消或重复开放")
        elif kind == "CANCEL_ROUTE":
            occupied = [name for name in route["sections"] + route["protection_sections"] if session.sections[name]["occupied"]]
            if occupied:
                result = reject("SECTION_OCCUPIED", "进路区段占用，不允许总取消", occupied)
            else:
                session.signals[route["signal"]].update(aspect=None, route=None, close_reason="CANCELLED")
                service._event(session, "signal_close", f"{route['signal']} 因总取消关闭", route["route_id"])
                for s in [*session.sections.values(), *session.switches.values()]:
                    s["owners"].discard(target)
                route.update(status="cancelled", remaining=set(), release_due={})
                result = success("总取消完成，信号关闭，进路锁闭已释放")
        elif route["status"] != "closed_locked":
            result = reject("SIGNAL_NOT_CLOSED", "信号未因故关闭，无需重复开放")
        else:
            fact = service._blocking_fact(session, service.routes[route["route_id"]], route["id"])
            if fact:
                result = service._reject(session, fact[1], route["route_id"], fact[0], fact[2])
            else:
                session.signals[route["signal"]].update(aspect=service.routes[route["route_id"]]["aspect"], close_reason=None)
                route["status"] = "signal_open"
                result = success(f"{route['signal']} 已重复开放，原进路锁闭保持")
        if route:
            result["route_id"] = route["route_id"]
    else:
        result = reject("UNKNOWN_COMMAND", "本期未开放此命令")
    # A command can emit multiple engine events (alignment, lock, signal).
    result["snapshot"] = service._snapshot(session)
    result.setdefault("reason_code", "OK" if result["accepted"] else "INVALID_OPERATION")
    result.setdefault("devices", [target] if target else [])
    result.setdefault("route_id", next((e["route_id"] for e in reversed(session.events) if e["version"] > start and e.get("route_id")), None))
    if result["accepted"]:
        if result.get("route_id"):
            definition = service.routes[result["route_id"]]
            result["devices"] = [definition["signal"], *definition["sections"]]
        elif kind.startswith("SWITCH_") or "INDICATION" in kind:
            result["devices"] = group_ids(service, target)
    result["engine_events"] = [deepcopy(e) for e in session.events if e["version"] > start]
    result["state_delta"] = {key: {name: {"before": before[key][name], "after": state}
                                  for name, state in result["snapshot"][key].items() if before[key][name] != state}
                             for key in ("sections", "switches", "signals")}
    return result
