"""Pure rule helpers for interlocking checks."""

from app.models.route_state import RouteState
from app.services.interlocking.constants import ROUTE_LOCKED, SECTION_CLEAR, SIGNAL_CLOSED


def find_locked_switch_owner(active_routes: list[RouteState], switch_code: str) -> RouteState | None:
    """Return the locked route that currently owns a switch."""

    for route_state in active_routes:
        if route_state.status == ROUTE_LOCKED and switch_code in route_state.locked_switches:
            return route_state
    return None


def find_locked_section_owners(active_routes: list[RouteState], section_code: str) -> list[RouteState]:
    """Return locked routes that contain a section."""

    return [
        route_state
        for route_state in active_routes
        if route_state.status == ROUTE_LOCKED and section_code in route_state.locked_sections
    ]


def validate_sections_clear(
    section_states: dict[str, dict[str, str]],
    section_codes: list[str],
) -> list[str]:
    """Return failed section rules for occupied sections."""

    failed_rules: list[str] = []
    for section_code in section_codes:
        state = section_states.get(section_code, {}).get("occupancy", SECTION_CLEAR)
        if state != SECTION_CLEAR:
            failed_rules.append(f"区段{section_code}已占用")
    return failed_rules


def validate_signal_closed(
    signal_states: dict[str, dict[str, str]],
    signal_code: str,
) -> list[str]:
    """Return failed signal rules if the entry signal is already open."""

    state = signal_states.get(signal_code, {}).get("aspect", SIGNAL_CLOSED)
    if state != SIGNAL_CLOSED:
        return [f"信号机{signal_code}已开放"]
    return []


def validate_no_hostile_route(
    active_routes: list[RouteState],
    hostile_routes: list[str],
) -> list[str]:
    """Return failed hostile-route rules."""

    active_route_names = {route_state.route_name for route_state in active_routes}
    conflict_names = sorted(active_route_names.intersection(set(hostile_routes)))
    if conflict_names:
        return [f"敌对进路已建立：{', '.join(conflict_names)}"]
    return []
