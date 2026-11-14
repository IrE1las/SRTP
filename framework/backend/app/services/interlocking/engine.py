"""6502-style interlocking core engine."""

from sqlalchemy.orm import Session

from app.models.interlocking_table import InterlockingTable
from app.models.route_state import RouteState
from app.schemas.interlocking import (
    InterlockingActionResponse,
    RouteConditionCheckResponse,
    StationSnapshotResponse,
)
from app.services.interlocking.constants import (
    DEVICE_SECTION,
    DEVICE_SIGNAL,
    DEVICE_SWITCH,
    ROUTE_LOCKED,
    SECTION_CLEAR,
    SECTION_OCCUPIED,
    SIGNAL_CLOSED,
    SIGNAL_OPEN,
)
from app.services.interlocking.repository import InterlockingRepository
from app.services.interlocking.rules import (
    find_locked_section_owners,
    find_locked_switch_owner,
    validate_no_hostile_route,
    validate_sections_clear,
    validate_signal_closed,
)


class InterlockingEngine:
    """6502 electric centralized interlocking core engine."""

    def __init__(self, db: Session, station_id: int) -> None:
        self.db = db
        self.station_id = station_id
        self.repository = InterlockingRepository(db, station_id)

    def get_station_snapshot(self) -> StationSnapshotResponse:
        """Return the current station runtime state."""

        return StationSnapshotResponse.model_validate(self.repository.build_snapshot())

    def check_route_conditions(self, entry_signal: str, exit_signal: str) -> RouteConditionCheckResponse:
        """Check switch, section, hostile-route and signal conditions."""

        route_table = self.repository.get_route_table(entry_signal, exit_signal)
        if route_table is None:
            return RouteConditionCheckResponse(
                ok=False,
                message="联锁表中未找到该进路",
                failed_rules=["进路不存在"],
            )

        failed_rules = self._collect_failed_rules(route_table)
        return RouteConditionCheckResponse(
            ok=not failed_rules,
            message="进路条件满足" if not failed_rules else failed_rules[0],
            failed_rules=failed_rules,
            route_name=route_table.route_name,
        )

    def arrange_route(self, entry_signal: str, exit_signal: str) -> InterlockingActionResponse:
        """Arrange a route: select route, lock it and open the entry signal."""

        route_table = self.repository.get_route_table(entry_signal, exit_signal)
        if route_table is None:
            return self._response(False, "联锁表中未找到该进路")

        failed_rules = self._collect_failed_rules(route_table)
        if failed_rules:
            return self._response(False, failed_rules[0])

        for switch_code, position in route_table.switches_required.items():
            self.repository.upsert_device_state(
                DEVICE_SWITCH,
                switch_code,
                {"position": position, "locked": True},
            )
        for section_code in route_table.sections_required:
            section_state = self.repository.get_device_state(DEVICE_SECTION, section_code)
            occupancy = SECTION_CLEAR
            if section_state is not None:
                occupancy = section_state.state_payload.get("occupancy", SECTION_CLEAR)
            self.repository.upsert_device_state(
                DEVICE_SECTION,
                section_code,
                {"occupancy": occupancy, "locked": True},
            )

        self.repository.create_locked_route(route_table)
        self.repository.upsert_device_state(DEVICE_SIGNAL, entry_signal, {"aspect": SIGNAL_OPEN})
        self.db.commit()
        return self._response(True, f"进路{route_table.route_name}办理成功")

    def cancel_route(self, signal_code: str) -> InterlockingActionResponse:
        """Cancel a locked route opened by the given entry signal."""

        route_state = self.repository.get_active_route_by_signal(signal_code)
        if route_state is None:
            return self._response(False, "未找到可取消的锁闭进路")

        self.repository.close_signal(signal_code)
        self._unlock_route_devices(route_state)
        self.repository.cancel_route(route_state)
        self.db.commit()
        return self._response(True, f"进路{route_state.route_name}已取消")

    def manual_unlock(self, section_code: str) -> InterlockingActionResponse:
        """Manually unlock resources related to a section."""

        active_routes = self.repository.list_active_routes()
        matched_routes = find_locked_section_owners(active_routes, section_code)
        if not matched_routes:
            section_state = self.repository.get_device_state(DEVICE_SECTION, section_code)
            if section_state is not None:
                section_payload = dict(section_state.state_payload)
                section_payload["locked"] = False
                self.repository.upsert_device_state(DEVICE_SECTION, section_code, section_payload)
                self.db.commit()
                return self._response(True, f"区段{section_code}已人工解锁")
            return self._response(False, "未找到与该区段相关的锁闭资源")

        for route_state in matched_routes:
            self.repository.close_signal(route_state.entry_signal)
            self._unlock_route_devices(route_state)
            self.repository.release_route(route_state)
        self.db.commit()
        return self._response(True, f"区段{section_code}相关进路已人工解锁")

    def operate_switch(self, switch_code: str, target_position: str) -> InterlockingActionResponse:
        """Manually operate a switch if it is not locked by a route."""

        locked_owner = find_locked_switch_owner(self.repository.list_active_routes(), switch_code)
        if locked_owner is not None:
            return self._response(False, "道岔已被进路锁闭")

        self.repository.upsert_device_state(
            DEVICE_SWITCH,
            switch_code,
            {"position": target_position, "locked": False},
        )
        self.db.commit()
        return self._response(True, f"道岔{switch_code}已转换至{target_position}")

    def check_hostile_routes(self, entry_signal: str, exit_signal: str) -> list[str]:
        """Check hostile routes using route-table explicit hostile definitions."""

        route_table = self.repository.get_route_table(entry_signal, exit_signal)
        if route_table is None:
            return ["进路不存在"]
        return validate_no_hostile_route(self.repository.list_active_routes(), route_table.hostile_routes)

    def update_section_occupancy(self, section_code: str, occupied: bool) -> InterlockingActionResponse:
        """Update section occupancy and close related open signals immediately."""

        state = SECTION_OCCUPIED if occupied else SECTION_CLEAR
        existing_state = self.repository.get_device_state(DEVICE_SECTION, section_code)
        locked = False
        if existing_state is not None:
            locked = bool(existing_state.state_payload.get("locked", False))
        self.repository.upsert_device_state(
            DEVICE_SECTION,
            section_code,
            {"occupancy": state, "locked": locked},
        )

        if occupied:
            for route_state in find_locked_section_owners(self.repository.list_active_routes(), section_code):
                self.repository.close_signal(route_state.entry_signal)
                route_state.opened_signal = None

        self.db.commit()
        return self._response(True, f"区段{section_code}状态已更新为{state}")

    def _collect_failed_rules(self, route_table: InterlockingTable) -> list[str]:
        signal_states = self.repository.get_state_map(DEVICE_SIGNAL)
        section_states = self.repository.get_state_map(DEVICE_SECTION)
        active_routes = self.repository.list_active_routes()

        failed_rules: list[str] = []
        failed_rules.extend(validate_sections_clear(section_states, route_table.sections_required))
        failed_rules.extend(validate_signal_closed(signal_states, route_table.entry_signal))
        failed_rules.extend(validate_no_hostile_route(active_routes, route_table.hostile_routes))

        for switch_code in route_table.switches_required:
            locked_owner = find_locked_switch_owner(active_routes, switch_code)
            if locked_owner is not None:
                failed_rules.append(f"道岔{switch_code}已被进路锁闭")
        return failed_rules

    def _unlock_route_devices(self, route_state: RouteState) -> None:
        for switch_code, position in route_state.locked_switches.items():
            self.repository.upsert_device_state(
                DEVICE_SWITCH,
                switch_code,
                {"position": position, "locked": False},
            )
        for section_code in route_state.locked_sections:
            section_state = self.repository.get_device_state(DEVICE_SECTION, section_code)
            occupancy = SECTION_CLEAR
            if section_state is not None:
                occupancy = section_state.state_payload.get("occupancy", SECTION_CLEAR)
            self.repository.upsert_device_state(
                DEVICE_SECTION,
                section_code,
                {"occupancy": occupancy, "locked": False},
            )

    def _response(self, success: bool, message: str) -> InterlockingActionResponse:
        return InterlockingActionResponse(
            success=success,
            message=message,
            snapshot=self.get_station_snapshot(),
        )
