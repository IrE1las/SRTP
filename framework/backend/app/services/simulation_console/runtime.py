"""Session-isolated, conservative first-stage teaching interlocking runtime.

This simulator is intentionally separate from the legacy exercise engine.
Experiment commands extend this same state machine through commands.py.
Manual unlocking and arbitrary train moves remain unsupported.
Its decisions are traceable to the supplied TB/T 3027, 3578 and 3537 copies and
to the imported workbook rows; it is not safety-certified railway software.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from copy import deepcopy
from threading import RLock
from time import monotonic
from uuid import uuid4

from .station import station_package


class SimulationError(Exception):
    """Invalid session, stale command or forbidden operation."""


@dataclass
class RuntimeSession:
    id: str
    owner_id: int
    interval_available: bool
    version: int = 0
    selected: list[str] = field(default_factory=list)
    selection_deadline: float | None = None
    sections: dict[str, dict] = field(default_factory=dict)
    switches: dict[str, dict] = field(default_factory=dict)
    signals: dict[str, dict] = field(default_factory=dict)
    routes: dict[str, dict] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    last_message: str = "仿真会话已准备；区段空闲，道岔定位，信号关闭。"
    mutex: RLock = field(default_factory=RLock, repr=False)


class SimulationService:
    def __init__(self) -> None:
        self.package = station_package()
        self.routes = {route["id"]: route for route in self.package["routes"]}
        self.buttons = {button["name"]: button for button in self.package["buttons"]}
        self.section_defs = {section["name"]: section for section in self.package["sections"]}
        self.switch_defs = {switch["id"]: switch for switch in self.package["switches"]}
        self.sessions: dict[str, RuntimeSession] = {}
        self.sessions_mutex = RLock()

    def new_session(self, owner_id: int, interval_available: bool = True,
                    occupied_sections: list[str] | None = None) -> dict:
        session = RuntimeSession(id=str(uuid4()), owner_id=owner_id, interval_available=interval_available)
        session.sections = {item["name"]: {"occupied": False, "occupancy_kind": "clear", "occupancy_origin": "preset", "owners": set()}
                            for item in self.package["sections"]}
        session.switches = {item["id"]: {"position": 0, "represented": True, "manual_locked": False, "sealed": False, "owners": set()}
                            for item in self.package["switches"]}
        session.signals = {item["name"]: {"aspect": None, "route": None}
                           for item in self.package["signals"]}
        for name in occupied_sections or []:
            if name not in session.sections:
                raise SimulationError(f"预置占用区段 {name} 不在本站配置中")
            session.sections[name]["occupied"] = True
            session.sections[name]["occupancy_kind"] = "vehicle"
        self._event(session, "session", "新建独立仿真会话；普通站内区间许可已预置" if interval_available
                    else "新建条件反例会话；区间许可未具备")
        if occupied_sections:
            self._event(session, "scenario", f"教学场景预置占用：{'、'.join(occupied_sections)}")
        with self.sessions_mutex:
            self.sessions[session.id] = session
        return self._snapshot(session)

    def _get(self, session_id: str, owner_id: int) -> RuntimeSession:
        with self.sessions_mutex:
            session = self.sessions.get(session_id)
        if session is None or session.owner_id != owner_id:
            raise SimulationError("仿真会话不存在或无权访问；请新建会话")
        return session

    @staticmethod
    def _event(session: RuntimeSession, kind: str, message: str, route_id: str | None = None) -> None:
        session.version += 1
        session.last_message = message
        session.events.append({"version": session.version, "time": datetime.now(timezone.utc).isoformat(),
                               "kind": kind, "message": message, "route_id": route_id})
        if len(session.events) > 500:
            session.events.pop(0)

    @staticmethod
    def _verify_version(session: RuntimeSession, version: int | None) -> None:
        if version is not None and version != session.version:
            raise SimulationError("状态版本已变化；请刷新操作台后重试")

    def _release_due(self, session: RuntimeSession) -> None:
        now = monotonic()
        for instance in session.routes.values():
            if instance["status"] in {"released", "cancelled"}:
                continue
            for section_name, due in list(instance["release_due"].items()):
                if due > now or session.sections[section_name]["occupied"]:
                    continue
                if section_name in instance["remaining"]:
                    instance["remaining"].remove(section_name)
                    session.sections[section_name]["owners"].discard(instance["id"])
                    self._event(session, "section_release", f"{section_name} 完成三点检查并延时 3 秒，正常解锁",
                                instance["route_id"])
                del instance["release_due"][section_name]
                for switch_id in instance["switches"]:
                    switch_section = self.switch_defs[switch_id]["section"]
                    if switch_section == section_name or (switch_section not in instance["sections"] and not instance["remaining"]):
                        session.switches[switch_id]["owners"].discard(instance["id"])
            if not instance["remaining"] and instance["progress"] >= len(instance["sections"]):
                for section_name in instance["protection_sections"]:
                    session.sections[section_name]["owners"].discard(instance["id"])
                for switch_id in instance["switches"]:
                    session.switches[switch_id]["owners"].discard(instance["id"])
                instance["status"] = "released"
                self._event(session, "route_release", f"进路 {instance['route_id']} 已按正常行车顺序全部解锁",
                            instance["route_id"])

    def _expire_selection(self, session: RuntimeSession) -> None:
        if session.selected and session.selection_deadline is not None and monotonic() >= session.selection_deadline:
            session.selected = []
            session.selection_deadline = None
            self._event(session, "selection_timeout", "始端选择超过 15 秒，临时按钮序列已清除")

    def _snapshot(self, session: RuntimeSession) -> dict:
        remaining = max(0, int(session.selection_deadline - monotonic() + 0.99)) if session.selection_deadline else 0
        result = {
            "session_id": session.id, "version": session.version,
            "interval_available": session.interval_available,
            "selected_buttons": list(session.selected), "selection_remaining_seconds": remaining,
            "last_message": session.last_message,
            "sections": {name: {"occupied": state["occupied"], "locked": bool(state["owners"]),
                                 "occupancy_kind": state.get("occupancy_kind", "clear"),
                                 "occupancy_origin": state.get("occupancy_origin", "preset"),
                                 "owners": sorted(state["owners"])} for name, state in session.sections.items()},
            "switches": {name: {"position": state["position"], "represented": state["represented"],
                                 "manual_locked": state.get("manual_locked", False), "sealed": state.get("sealed", False),
                                 "locked": bool(state["owners"]), "owners": sorted(state["owners"])}
                         for name, state in session.switches.items()},
            "signals": {name: dict(state) for name, state in session.signals.items()},
            "routes": [{"id": instance["id"], "route_id": instance["route_id"],
                        "kind": instance["kind"], "status": instance["status"],
                        "sections": instance["sections"], "remaining_sections": sorted(instance["remaining"]),
                        "progress": instance["progress"], "signal": instance["signal"]}
                       for instance in session.routes.values()],
            "events": session.events[-60:],
        }
        if not session.history or session.history[-1]["version"] != session.version:
            session.history.append(deepcopy(result))
            if len(session.history) > 120:
                session.history.pop(0)
        return result

    def snapshot(self, session_id: str, owner_id: int) -> dict:
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._expire_selection(session)
            self._release_due(session)
            return self._snapshot(session)

    def replay_frames(self, session_id: str, owner_id: int) -> list[dict]:
        """Read-only snapshots captured after each command or timed release."""
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._expire_selection(session)
            self._release_due(session)
            self._snapshot(session)
            return deepcopy(session.history)

    def _reject(self, session: RuntimeSession, message: str, route_id: str | None = None,
                reason_code: str = "INVALID_OPERATION", devices: list[str] | None = None) -> dict:
        self._event(session, "rejected", message, route_id)
        session.events[-1].update(reason_code=reason_code, devices=devices or [])
        return {"accepted": False, "message": message, "reason_code": reason_code,
                "devices": devices or [], "snapshot": self._snapshot(session)}

    def _conditional_sections(self, session: RuntimeSession, route: dict) -> list[str]:
        sections = route["overlap_sections"]
        condition = route["overlap_condition"]
        if not sections:
            return []
        if not condition:
            return sections  # Unknown condition is checked conservatively.
        from .station import _switches
        demands, errors = _switches(condition)
        if errors or not demands:
            raise SimulationError(f"进路 {route['id']} 超限区段条件无法核验")
        if all(session.switches.get(sid, {}).get("position") == pos for sid, pos in demands.items()):
            return sections
        return []

    @staticmethod
    def _hostile_names(route: dict) -> set[str]:
        return {str(name).split("#")[0] for name in route["hostile_signals"]}

    def _blocking_fact(self, session: RuntimeSession, route: dict, ignore_instance=None):
        """Stable rejection facts; no state is mutated during validation."""
        if route["status"] != "ready":
            return "DATA_BLOCKED", f"进路 {route['id']} 数据待核对，不能办理", []
        if route["attribute"] in {12, 14} and not session.interval_available:
            return "INTERVAL_UNAVAILABLE", "区间许可未具备，出站信号不得开放", [route["signal"]]
        try:
            conditional = self._conditional_sections(session, route)
        except SimulationError as exc:
            return "DATA_BLOCKED", str(exc), []
        # Occupancy and indication precede locking/conflict checks.
        for name in route["sections"] + conditional:
            state = session.sections[name]
            if state["occupied"]:
                exception = (route["kind"] == "short_shunt" and name == route["sections"][-1]
                             and not self.section_defs[name]["switches"])
                if not exception:
                    return "SECTION_OCCUPIED", f"区段 {name} 已占用", [name]
        for sid, pos in route["switches"].items():
            state = session.switches[sid]
            if not state["represented"]:
                return "SWITCH_UNREPRESENTED", f"道岔 {sid} 无表示，不能构成进路", [sid]
            section = self.switch_defs[sid]["section"]
            if state["position"] != pos and session.sections.get(section, {}).get("occupied"):
                return "SECTION_OCCUPIED", f"道岔 {sid} 所在区段 {section} 占用，不能转换", [section, sid]
        for sid, pos in route["switches"].items():
            state = session.switches[sid]
            if state.get("sealed"):
                return "SEALED_FOR_ROUTE", f"道岔 {sid} 已封闭，不能纳入新进路", [sid]
            if state.get("manual_locked") and state["position"] != pos:
                return "SWITCH_MANUAL_LOCKED", f"道岔 {sid} 单锁在不符位置，不能转换", [sid]
        for instance in session.routes.values():
            if instance["id"] == ignore_instance or instance["status"] in {"released", "cancelled"}:
                continue
            other = self.routes[instance["route_id"]]
            if other["signal"] == route["signal"]:
                return "SIGNAL_ROUTE_LOCKED", f"{route['signal']} 上一条进路尚未解锁", [route["signal"]]
            if (other["signal"] in self._hostile_names(route) or
                    route["signal"] in self._hostile_names(other)):
                return "HOSTILE_ROUTE", f"与已建立的 {instance['route_id']} 号进路敌对", [other["signal"], route["signal"]]
        for name in route["sections"] + conditional:
            if session.sections[name]["owners"] - {ignore_instance}:
                return "SECTION_LOCKED", f"区段 {name} 已被其他进路锁闭", [name]
        for sid in route["switches"]:
            if session.switches[sid]["owners"] - {ignore_instance}:
                return "SWITCH_ROUTE_LOCKED", f"道岔 {sid} 已被其他进路锁闭", [sid]
        return None

    def _blocking_reason(self, session, route):
        fact = self._blocking_fact(session, route)
        return fact[1] if fact else None

    def _arrange(self, session: RuntimeSession, route: dict) -> dict:
        fact = self._blocking_fact(session, route)
        session.selected = []
        session.selection_deadline = None
        if fact:
            return self._reject(session, fact[1], route["id"], fact[0], fact[2])
        instance_id = str(uuid4())
        conditional_sections = self._conditional_sections(session, route)
        self._event(session, "route_check", f"进路 {route['id']} 条件检查通过", route["id"])
        for switch_id, position in route["switches"].items():
            session.switches[switch_id]["position"] = position
        self._event(session, "switch_align", f"进路 {route['id']} 道岔选动完成并核对表示", route["id"])
        for switch_id in route["switches"]:
            session.switches[switch_id]["owners"].add(instance_id)
        for section_name in set(route["sections"] + conditional_sections):
            session.sections[section_name]["owners"].add(instance_id)
        for sub_id in route["subroutes"]:
            self._event(session, "subroute_lock", f"组合进路基本段 {sub_id} 已纳入锁闭", route["id"])
        self._event(session, "route_lock", f"进路 {route['id']} 预先锁闭", route["id"])
        session.signals[route["signal"]] = {"aspect": route["aspect"], "route": route["id"]}
        session.routes[instance_id] = {
            "id": instance_id, "route_id": route["id"], "kind": route["kind"],
            "signal": route["signal"], "sections": list(route["sections"]),
            "protection_sections": conditional_sections,
            "approach_section": route["approach_section"] if route["approach_section"] in session.sections
            and route["approach_section"] not in route["sections"] else None,
            "remaining": set(route["sections"]), "switches": list(route["switches"]),
            "progress": -2 if route["approach_section"] in session.sections
            and route["approach_section"] not in route["sections"] else -1,
            "status": "signal_open", "release_due": {}, "train_started": False,
        }
        message = f"进路 {route['id']} 已锁闭，{route['signal']} 显示 {route['aspect']}"
        self._event(session, "signal_open", message, route["id"])
        return {"accepted": True, "message": message, "snapshot": self._snapshot(session)}

    def select_button(self, session_id: str, owner_id: int, button: str, version: int | None = None) -> dict:
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._release_due(session)
            self._expire_selection(session)
            self._verify_version(session, version)
            if button not in self.buttons:
                return self._reject(session, f"按钮 {button} 不在本站配置中")
            proposed = session.selected + [button]
            matching = [route for route in self.package["routes"]
                        if route["status"] != "excluded" and route["button_sequence"][:len(proposed)] == proposed]
            if not matching:
                session.selected = []
                session.selection_deadline = None
                return self._reject(session, f"按钮序列 {' → '.join(proposed)} 不在本阶段候选进路中")
            exact = [route for route in matching if len(route["button_sequence"]) == len(proposed)]
            if exact:
                if len(exact) != 1:
                    session.selected = []
                    session.selection_deadline = None
                    return self._reject(session, "完整按钮序列对应多条进路，数据冲突，未开放信号")
                return self._arrange(session, exact[0])
            session.selected = proposed
            if len(proposed) == 1:
                session.selection_deadline = monotonic() + 15
            self._event(session, "button_select", f"已选 {' → '.join(proposed)}；等待下一按钮")
            return {"accepted": True, "message": session.last_message, "snapshot": self._snapshot(session)}

    def clear_selection(self, session_id: str, owner_id: int, version: int | None = None) -> dict:
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._release_due(session)
            self._verify_version(session, version)
            session.selected = []
            session.selection_deadline = None
            self._event(session, "selection_clear", "临时按钮选择已清除；已锁闭进路保持不变")
            return {"accepted": True, "message": session.last_message, "snapshot": self._snapshot(session)}

    def step_train(self, session_id: str, owner_id: int, instance_id: str, version: int | None = None) -> dict:
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._release_due(session)
            self._verify_version(session, version)
            instance = session.routes.get(instance_id)
            if not instance:
                return self._reject(session, "进路实例不存在")
            if instance["status"] in {"released", "cancelled", "closed_locked"}:
                return self._reject(session, "该进路已完成正常解锁")
            if instance["progress"] == -2:
                approach = instance["approach_section"]
                if session.sections[approach]["occupied"]:
                    return self._reject(session, f"接近区段 {approach} 已有车辆占用", instance["route_id"])
                instance["train_started"] = True
                session.sections[approach].update(occupied=True, occupancy_kind="vehicle", occupancy_origin="simulation")
                instance["progress"] = -1
                instance["status"] = "approaching"
                self._event(session, "train_approach", f"仿真车辆接近 {approach}；信号保持开放",
                            instance["route_id"])
                return {"accepted": True, "message": session.last_message, "snapshot": self._snapshot(session)}
            sections = instance["sections"]
            next_index = instance["progress"] + 1
            if next_index < len(sections):
                next_section = sections[next_index]
                if session.sections[next_section]["occupied"]:
                    return self._reject(session, f"区段 {next_section} 已占用，仿真行车不能越过", instance["route_id"])
                instance["train_started"] = True
                session.sections[next_section].update(occupied=True, occupancy_kind="vehicle", occupancy_origin="simulation")
                self._event(session, "train_enter", f"车辆进入 {next_section}", instance["route_id"])
                if next_index == 0 and instance["approach_section"]:
                    approach = instance["approach_section"]
                    session.sections[approach].update(occupied=False, occupancy_kind="clear", occupancy_origin="simulation")
                    self._event(session, "approach_clear", f"车辆出清接近区段 {approach}", instance["route_id"])
                if next_index == 0 and instance["kind"] == "train":
                    session.signals[instance["signal"]] = {"aspect": None, "route": None}
                    self._event(session, "signal_close", f"列车第一轮对进入信号机内方，{instance['signal']} 关闭",
                                instance["route_id"])
                if next_index > 0:
                    previous = sections[next_index - 1]
                    session.sections[previous].update(occupied=False, occupancy_kind="clear", occupancy_origin="simulation")
                    instance["release_due"][previous] = monotonic() + 3
                    self._event(session, "train_clear", f"车辆出清 {previous}；三点检查后延时解锁",
                                instance["route_id"])
                    if instance["kind"] != "train" and session.signals[instance["signal"]]["aspect"] is not None:
                        session.signals[instance["signal"]] = {"aspect": None, "route": None}
                        self._event(session, "signal_close", f"调车车辆全部越过 {instance['signal']}，信号关闭",
                                    instance["route_id"])
                instance["progress"] = next_index
                instance["status"] = "running"
            else:
                last = sections[-1]
                if not session.sections[last]["occupied"]:
                    return self._reject(session, "末端区段未被仿真车辆占用，不能宣布出清", instance["route_id"])
                session.sections[last].update(occupied=False, occupancy_kind="clear", occupancy_origin="simulation")
                instance["release_due"][last] = monotonic() + 3
                instance["progress"] = len(sections)
                instance["status"] = "clearing"
                session.signals[instance["signal"]] = {"aspect": None, "route": None}
                self._event(session, "train_exit", f"车辆出清末端 {last}；等待三点检查和 3 秒延时",
                            instance["route_id"])
            return {"accepted": True, "message": session.last_message, "snapshot": self._snapshot(session)}


simulation_service = SimulationService()
