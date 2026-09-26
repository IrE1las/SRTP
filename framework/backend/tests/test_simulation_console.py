"""End-to-end checks for the isolated data.xls teaching simulation runtime."""

from collections import Counter

import pytest

from app.services.simulation_console import runtime
from app.services.simulation_console.geometry_audit import audit_geometry
from app.services.simulation_console.station import station_package


def _press(service, session, buttons, owner=10):
    response = None
    for button in buttons:
        response = service.select_button(session["session_id"], owner, button, session["version"])
        session = response["snapshot"]
    return response


def test_workbook_counts_and_every_candidate_has_a_result():
    package = station_package()
    assert package["counts"] == {
        "signals": 32, "switches": 25, "sections": 43, "buttons": 64,
        "switch_buttons": 15, "candidate_routes": 208,
        "ready_routes": 193, "blocked_routes": 15, "excluded_routes": 4,
    }
    assert Counter(route["status"] for route in package["routes"]) == {
        "ready": 193, "blocked": 15, "excluded": 4,
    }
    assert len(package["boundaries"]) == 57
    assert {joint["shape"] for joint in package["boundaries"]} == {0, 1, 2, 3}
    assert sum(joint["infringing"] for joint in package["boundaries"]) == 2
    assert {label["text"] for label in package["labels"]} == {
        "联锁测试站", "北京方面", "天津方面", "东郊方面", "编组线", "牵出线",
    }
    turnout_five = next(point for point in package["switches"] if point["id"] == "5")
    assert (turnout_five["front_x"], turnout_five["x"], turnout_five["break_x"]) == (355, 380, 405)
    turnout_eighteen = next(point for point in package["switches"] if point["id"] == "18")
    assert (turnout_eighteen["back_x"], turnout_eighteen["x"]) == (1104, 1295)
    sections = {section["name"]: section for section in package["sections"]}
    assert (sections["21DG"]["draw_x2"], sections["25DG"]["draw_x1"]) == (730, 730)
    assert (sections["2DG"]["draw_x2"], sections["D2G"]["draw_x1"]) == (1650, 1650)
    turnout_two = next(point for point in package["switches"] if point["id"] == "2")
    assert turnout_two["front_x"] == 1670 and turnout_two["draw_front_x"] == 1650
    assert "209" in {route["id"] for route in package["routes"] if route["status"] == "blocked"}


def test_drawn_tracks_have_only_the_seven_external_open_ends():
    audit = audit_geometry()
    assert audit["edge_count"] == 143
    assert audit["unsupported_joints"] == []
    assert {tuple(item["point"]) for item in audit["open_ends"]} == {
        (200, 445), (50, 545), (50, 645), (1054, 245),
        (1725, 345), (1875, 545), (1875, 645),
    }


def test_every_ready_route_can_be_selected_driven_and_normally_released(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(runtime, "monotonic", lambda: clock[0])
    service = runtime.SimulationService()
    for route in service.package["routes"]:
        if route["status"] != "ready":
            continue
        session = service.new_session(10)
        response = _press(service, session, route["button_sequence"])
        assert response["accepted"], (route["id"], response["message"])
        session = response["snapshot"]
        assert session["signals"][route["signal"]]["aspect"] == route["aspect"]
        instance = session["routes"][0]
        approach_steps = int(session["routes"][0]["progress"] == -2)
        for _ in range(len(route["sections"]) + 1 + approach_steps):
            response = service.step_train(session["session_id"], 10, instance["id"], session["version"])
            assert response["accepted"], (route["id"], response["message"])
            session = response["snapshot"]
            assert all(session["sections"][name]["locked"] for name in route["sections"]
                       if session["sections"][name]["occupied"])
        assert session["signals"][route["signal"]]["aspect"] is None
        assert session["routes"][0]["status"] == "clearing"
        clock[0] += 3.1
        session = service.snapshot(session["session_id"], 10)
        assert session["routes"][0]["status"] == "released", route["id"]
        assert not any(state["occupied"] or state["locked"] for state in session["sections"].values())
        assert not any(state["locked"] for state in session["switches"].values())


def test_blocked_route_never_opens_a_signal():
    service = runtime.SimulationService()
    route = service.routes["209"]
    session = service.new_session(10)
    response = _press(service, session, route["button_sequence"])
    assert not response["accepted"]
    assert not response["snapshot"]["routes"]
    assert all(state["aspect"] is None for state in response["snapshot"]["signals"].values())


def test_selection_clear_does_not_release_locked_route():
    service = runtime.SimulationService()
    session = service.new_session(10)
    response = _press(service, session, service.routes["1"]["button_sequence"])
    cleared = service.clear_selection(session["session_id"], 10, response["snapshot"]["version"])
    assert cleared["snapshot"]["routes"][0]["status"] == "signal_open"
    assert cleared["snapshot"]["signals"]["XN"]["aspect"] == "UU"


def test_departure_requires_preconfigured_interval_permission():
    service = runtime.SimulationService()
    session = service.new_session(10, interval_available=False)
    response = _press(service, session, service.routes["16"]["button_sequence"])
    assert not response["accepted"]
    assert "区间许可" in response["message"]
    assert not response["snapshot"]["routes"]


def test_occupied_switch_free_destination_is_short_shunt_only():
    service = runtime.SimulationService()
    short = service.new_session(10, occupied_sections=["1/19WG"])
    short_response = _press(service, short, service.routes["56"]["button_sequence"])
    assert short_response["accepted"]
    long = service.new_session(11, occupied_sections=["1/19WG"])
    long_response = _press(service, long, service.routes["115"]["button_sequence"], owner=11)
    assert not long_response["accepted"]
    assert "1/19WG" in long_response["message"]
    assert not long_response["snapshot"]["routes"]


def test_sessions_are_private_and_version_conflicts_are_rejected():
    service = runtime.SimulationService()
    first = service.new_session(10)
    second = service.new_session(11)
    response = _press(service, first, service.routes["1"]["button_sequence"])
    assert not service.snapshot(second["session_id"], 11)["routes"]
    with pytest.raises(runtime.SimulationError):
        service.snapshot(first["session_id"], 11)
    with pytest.raises(runtime.SimulationError):
        service.clear_selection(first["session_id"], 10, version=first["version"])
    assert response["snapshot"]["routes"]


def test_train_and_shunt_close_at_distinct_simulated_events():
    service = runtime.SimulationService()
    train = _press(service, service.new_session(10), service.routes["1"]["button_sequence"])["snapshot"]
    train_id = train["routes"][0]["id"]
    train = service.step_train(train["session_id"], 10, train_id, train["version"])["snapshot"]
    assert train["signals"]["XN"]["aspect"] == "UU"
    train = service.step_train(train["session_id"], 10, train_id, train["version"])["snapshot"]
    assert train["signals"]["XN"]["aspect"] is None
    shunt = _press(service, service.new_session(11), service.routes["56"]["button_sequence"], owner=11)["snapshot"]
    shunt_id = shunt["routes"][0]["id"]
    shunt = service.step_train(shunt["session_id"], 11, shunt_id, shunt["version"])["snapshot"]
    if shunt["routes"][0]["progress"] == -1:
        shunt = service.step_train(shunt["session_id"], 11, shunt_id, shunt["version"])["snapshot"]
    assert shunt["signals"]["D1"]["aspect"] == "B"
    shunt = service.step_train(shunt["session_id"], 11, shunt_id, shunt["version"])["snapshot"]
    assert shunt["signals"]["D1"]["aspect"] is None


def test_selection_expires_at_fifteen_seconds(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(runtime, "monotonic", lambda: clock[0])
    service = runtime.SimulationService()
    session = service.new_session(10)
    selected = service.select_button(session["session_id"], 10, "XNLA", session["version"])["snapshot"]
    assert selected["selected_buttons"] == ["XNLA"]
    assert selected["selection_remaining_seconds"] == 15
    clock[0] = 115.0
    expired = service.snapshot(session["session_id"], 10)
    assert expired["selected_buttons"] == []
    assert expired["events"][-1]["kind"] == "selection_timeout"


def test_replay_is_read_only_and_private():
    service = runtime.SimulationService()
    initial = service.new_session(10)
    arranged = _press(service, initial, service.routes["1"]["button_sequence"])["snapshot"]
    frames = service.replay_frames(initial["session_id"], 10)
    assert frames[0]["routes"] == []
    assert frames[-1]["routes"][0]["route_id"] == "1"
    frames[-1]["sections"].clear()
    assert service.snapshot(initial["session_id"], 10)["sections"]
    assert service.snapshot(initial["session_id"], 10)["version"] == arranged["version"]
    with pytest.raises(runtime.SimulationError):
        service.replay_frames(initial["session_id"], 11)
