"""Interlocking engine acceptance tests."""

from sqlalchemy.orm import Session

from app.services.interlocking.engine import InterlockingEngine


def test_arrange_x_to_i_route_locks_switches_and_opens_signal(
    db_session: Session,
    seeded_station: int,
) -> None:
    engine = InterlockingEngine(db_session, seeded_station)

    response = engine.arrange_route("X", "I")

    assert response.success is True
    snapshot = response.snapshot
    assert snapshot.switches["1#"]["position"] == "normal"
    assert snapshot.switches["3#"]["position"] == "normal"
    assert snapshot.switches["5#"]["position"] == "normal"
    assert snapshot.switches["1#"]["locked"] is True
    assert snapshot.signals["X"]["aspect"] == "open"
    assert "X至I道接车进路" in snapshot.locked_routes


def test_locked_switch_cannot_be_operated(db_session: Session, seeded_station: int) -> None:
    engine = InterlockingEngine(db_session, seeded_station)
    engine.arrange_route("X", "I")

    response = engine.operate_switch("1#", "reverse")

    assert response.success is False
    assert response.message == "道岔已被进路锁闭"
    assert response.snapshot.switches["1#"]["position"] == "normal"


def test_hostile_route_cannot_be_arranged(db_session: Session, seeded_station: int) -> None:
    engine = InterlockingEngine(db_session, seeded_station)
    engine.arrange_route("X", "I")

    response = engine.arrange_route("S", "IAG")

    assert response.success is False
    assert "敌对进路已建立" in response.message


def test_occupied_section_closes_signal_but_keeps_route_locked(
    db_session: Session,
    seeded_station: int,
) -> None:
    engine = InterlockingEngine(db_session, seeded_station)
    engine.arrange_route("X", "I")

    response = engine.update_section_occupancy("IAG", True)

    assert response.success is True
    assert response.snapshot.signals["X"]["aspect"] == "closed"
    assert "X至I道接车进路" in response.snapshot.locked_routes
    assert response.snapshot.sections["IAG"]["occupancy"] == "occupied"


def test_cancel_route_and_manual_unlock_release_resources(
    db_session: Session,
    seeded_station: int,
) -> None:
    engine = InterlockingEngine(db_session, seeded_station)
    engine.arrange_route("X", "I")

    cancel_response = engine.cancel_route("X")
    assert cancel_response.success is True
    assert cancel_response.snapshot.signals["X"]["aspect"] == "closed"
    assert "X至I道接车进路" not in cancel_response.snapshot.locked_routes
    assert cancel_response.snapshot.switches["1#"]["locked"] is False

    engine.arrange_route("X", "I")
    unlock_response = engine.manual_unlock("IAG")
    assert unlock_response.success is True
    assert "X至I道接车进路" not in unlock_response.snapshot.locked_routes
    assert unlock_response.snapshot.sections["IAG"]["locked"] is False
