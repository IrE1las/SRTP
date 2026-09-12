"""Repository helpers for interlocking engine state."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.device_state import DeviceState
from app.models.interlocking_table import InterlockingTable
from app.models.route_state import RouteState
from app.models.section import Section
from app.models.signal import Signal
from app.models.station import Station
from app.models.switch import Switch
from app.services.interlocking.constants import (
    ACTIVE_ROUTE_STATUSES,
    DEVICE_SECTION,
    DEVICE_SIGNAL,
    DEVICE_SWITCH,
    ROUTE_CANCELLED,
    ROUTE_LOCKED,
    ROUTE_RELEASED,
    SECTION_CLEAR,
    SIGNAL_CLOSED,
    SWITCH_NORMAL,
)


class InterlockingRepository:
    """Database access layer for interlocking runtime and static data."""

    def __init__(self, db: Session, station_id: int) -> None:
        self.db = db
        self.station_id = station_id

    def get_route_table(self, entry_signal: str, exit_signal: str) -> InterlockingTable | None:
        """Return the route table matching entry and exit signals."""

        return (
            self.db.query(InterlockingTable)
            .filter(
                InterlockingTable.station_id == self.station_id,
                InterlockingTable.entry_signal == entry_signal,
                InterlockingTable.exit_signal == exit_signal,
            )
            .first()
        )

    def list_route_tables(self) -> list[InterlockingTable]:
        """Return all route table entries for the station."""

        return (
            self.db.query(InterlockingTable)
            .filter(InterlockingTable.station_id == self.station_id)
            .order_by(InterlockingTable.id)
            .all()
        )

    def get_station_detail(self) -> dict[str, Any]:
        """Return station static data needed by the SVG canvas."""

        station = self.db.get(Station, self.station_id)
        return {
            "station": station,
            "signals": (
                self.db.query(Signal)
                .filter(Signal.station_id == self.station_id)
                .order_by(Signal.id)
                .all()
            ),
            "switches": (
                self.db.query(Switch)
                .filter(Switch.station_id == self.station_id)
                .order_by(Switch.id)
                .all()
            ),
            "sections": (
                self.db.query(Section)
                .filter(Section.station_id == self.station_id)
                .order_by(Section.id)
                .all()
            ),
            "routes": self.list_route_tables(),
        }

    def list_active_routes(self) -> list[RouteState]:
        """Return currently active locked routes."""

        return (
            self.db.query(RouteState)
            .filter(
                RouteState.station_id == self.station_id,
                RouteState.status.in_(ACTIVE_ROUTE_STATUSES),
            )
            .order_by(RouteState.id)
            .all()
        )

    def get_active_route_by_signal(self, signal_code: str) -> RouteState | None:
        """Return an active route opened by an entry signal."""

        return (
            self.db.query(RouteState)
            .filter(
                RouteState.station_id == self.station_id,
                RouteState.entry_signal == signal_code,
                RouteState.status == ROUTE_LOCKED,
            )
            .order_by(RouteState.id.desc())
            .first()
        )

    def get_device_state(self, device_type: str, device_code: str) -> DeviceState | None:
        """Return a single device runtime state."""

        return (
            self.db.query(DeviceState)
            .filter(
                DeviceState.station_id == self.station_id,
                DeviceState.device_type == device_type,
                DeviceState.device_code == device_code,
            )
            .first()
        )

    def upsert_device_state(
        self,
        device_type: str,
        device_code: str,
        state_payload: dict[str, Any],
    ) -> DeviceState:
        """Create or update a device state."""

        device_state = self.get_device_state(device_type, device_code)
        if device_state is None:
            device_state = DeviceState(
                station_id=self.station_id,
                device_type=device_type,
                device_code=device_code,
                state_payload=state_payload,
            )
            self.db.add(device_state)
        else:
            device_state.state_payload = state_payload
        self.db.flush()
        return device_state

    def get_state_map(self, device_type: str) -> dict[str, dict[str, Any]]:
        """Return runtime states keyed by device code."""

        states = (
            self.db.query(DeviceState)
            .filter(
                DeviceState.station_id == self.station_id,
                DeviceState.device_type == device_type,
            )
            .all()
        )
        return {state.device_code: state.state_payload for state in states}

    def create_locked_route(self, route_table: InterlockingTable) -> RouteState:
        """Persist a locked route state after successful arrangement."""

        route_state = RouteState(
            station_id=self.station_id,
            route_name=route_table.route_name,
            entry_signal=route_table.entry_signal,
            exit_signal=route_table.exit_signal,
            status=ROUTE_LOCKED,
            locked_switches=route_table.switches_required,
            locked_sections=route_table.sections_required,
            opened_signal=route_table.entry_signal,
            metadata_payload={"route_type": route_table.route_type},
        )
        self.db.add(route_state)
        self.db.flush()
        return route_state

    def cancel_route(self, route_state: RouteState) -> None:
        """Mark a route as cancelled and closed."""

        route_state.status = ROUTE_CANCELLED
        route_state.opened_signal = None
        route_state.cancelled_at = datetime.now(timezone.utc)
        self.db.flush()

    def release_route(self, route_state: RouteState) -> None:
        """Mark a route as manually released."""

        route_state.status = ROUTE_RELEASED
        route_state.opened_signal = None
        route_state.released_at = datetime.now(timezone.utc)
        self.db.flush()

    def close_signal(self, signal_code: str) -> None:
        """Close a signal device."""

        self.upsert_device_state(DEVICE_SIGNAL, signal_code, {"aspect": SIGNAL_CLOSED})

    def build_snapshot(self) -> dict[str, Any]:
        """Build a full runtime state snapshot for API responses."""

        signal_states = self.get_state_map(DEVICE_SIGNAL)
        switch_states = self.get_state_map(DEVICE_SWITCH)
        section_states = self.get_state_map(DEVICE_SECTION)

        for signal in self.db.query(Signal).filter(Signal.station_id == self.station_id).all():
            signal_states.setdefault(signal.signal_code, {"aspect": SIGNAL_CLOSED})
        for switch in self.db.query(Switch).filter(Switch.station_id == self.station_id).all():
            switch_states.setdefault(switch.switch_code, {"position": switch.normal_position or SWITCH_NORMAL})
        for section in self.db.query(Section).filter(Section.station_id == self.station_id).all():
            section_states.setdefault(section.section_code, {"occupancy": SECTION_CLEAR, "locked": False})

        active_routes = self.list_active_routes()
        return {
            "station_id": self.station_id,
            "signals": signal_states,
            "switches": switch_states,
            "sections": section_states,
            "active_routes": [
                {
                    "route_name": route.route_name,
                    "entry_signal": route.entry_signal,
                    "exit_signal": route.exit_signal,
                    "status": route.status,
                    "locked_switches": route.locked_switches,
                    "locked_sections": route.locked_sections,
                    "opened_signal": route.opened_signal,
                }
                for route in active_routes
            ],
            "locked_routes": [route.route_name for route in active_routes],
        }
