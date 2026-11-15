"""Seed service for standard station and runtime states."""

from sqlalchemy.orm import Session

from app.models.device_state import DeviceState
from app.models.interlocking_table import InterlockingTable
from app.models.route_state import RouteState
from app.models.section import Section
from app.models.signal import Signal
from app.models.station import Station
from app.models.switch import Switch
from app.services.interlocking.constants import (
    DEVICE_SECTION,
    DEVICE_SIGNAL,
    DEVICE_SWITCH,
    SECTION_CLEAR,
    SIGNAL_CLOSED,
)
from app.services.interlocking.seed_data import (
    STANDARD_ROUTES,
    STANDARD_SECTIONS,
    STANDARD_SIGNALS,
    STANDARD_STATION,
    STANDARD_SWITCHES,
)


def seed_default_station(db: Session) -> Station:
    """Create the standard station and route table if they do not exist."""

    station = (
        db.query(Station)
        .filter(Station.station_code == STANDARD_STATION["station_code"])
        .first()
    )
    if station is None:
        station = Station(**STANDARD_STATION)
        db.add(station)
        db.flush()

    _seed_signals(db, station.id)
    _seed_switches(db, station.id)
    _seed_sections(db, station.id)
    _seed_routes(db, station.id)
    db.commit()
    return station


def reset_station_runtime_state(db: Session, station_id: int) -> None:
    """Reset runtime states for a station without deleting static data."""

    db.query(RouteState).filter(RouteState.station_id == station_id).delete()
    db.query(DeviceState).filter(DeviceState.station_id == station_id).delete()

    for signal in db.query(Signal).filter(Signal.station_id == station_id).all():
        db.add(
            DeviceState(
                station_id=station_id,
                device_type=DEVICE_SIGNAL,
                device_code=signal.signal_code,
                state_payload={"aspect": SIGNAL_CLOSED},
            )
        )
    for switch in db.query(Switch).filter(Switch.station_id == station_id).all():
        db.add(
            DeviceState(
                station_id=station_id,
                device_type=DEVICE_SWITCH,
                device_code=switch.switch_code,
                state_payload={"position": switch.normal_position, "locked": False},
            )
        )
    for section in db.query(Section).filter(Section.station_id == station_id).all():
        db.add(
            DeviceState(
                station_id=station_id,
                device_type=DEVICE_SECTION,
                device_code=section.section_code,
                state_payload={"occupancy": SECTION_CLEAR, "locked": False},
            )
        )
    db.commit()


def _seed_signals(db: Session, station_id: int) -> None:
    existing_codes = {
        signal.signal_code
        for signal in db.query(Signal).filter(Signal.station_id == station_id).all()
    }
    for item in STANDARD_SIGNALS:
        if item["signal_code"] not in existing_codes:
            db.add(Signal(station_id=station_id, **item))


def _seed_switches(db: Session, station_id: int) -> None:
    existing_codes = {
        switch.switch_code
        for switch in db.query(Switch).filter(Switch.station_id == station_id).all()
    }
    for item in STANDARD_SWITCHES:
        if item["switch_code"] not in existing_codes:
            db.add(Switch(station_id=station_id, **item))


def _seed_sections(db: Session, station_id: int) -> None:
    existing_codes = {
        section.section_code
        for section in db.query(Section).filter(Section.station_id == station_id).all()
    }
    for item in STANDARD_SECTIONS:
        if item["section_code"] not in existing_codes:
            db.add(Section(station_id=station_id, **item))


def _seed_routes(db: Session, station_id: int) -> None:
    existing_names = {
        route.route_name
        for route in db.query(InterlockingTable).filter(InterlockingTable.station_id == station_id).all()
    }
    for item in STANDARD_ROUTES:
        if item["route_name"] not in existing_names:
            db.add(InterlockingTable(station_id=station_id, **item))
