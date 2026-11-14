"""Interlocking API acceptance tests."""

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    username = "api_student"
    password = "password123"
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "real_name": "接口学生",
            "role": "student",
            "student_id": "API001",
            "class_name": "信号一班",
        },
    )
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_interlocking_api_acceptance_flow(client: TestClient) -> None:
    headers = _auth_headers(client)

    seed_response = client.post("/api/interlocking/stations/seed-default", headers=headers)
    assert seed_response.status_code == 200
    station_id = seed_response.json()["station_id"]

    detail_response = client.get(
        f"/api/interlocking/stations/{station_id}/detail",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["station"]["station_config"]["canvas"]["width"] == 1100
    assert len(detail["signals"]) == 12
    assert len(detail["switches"]) == 10
    assert len(detail["sections"]) == 11
    assert len(detail["routes"]) >= 20

    reset_response = client.post(
        f"/api/interlocking/stations/{station_id}/reset-state",
        headers=headers,
    )
    assert reset_response.status_code == 200

    arrange_response = client.post(
        "/api/interlocking/routes/arrange",
        headers=headers,
        json={"station_id": station_id, "entry_signal": "X", "exit_signal": "I"},
    )
    assert arrange_response.status_code == 200
    snapshot = arrange_response.json()["snapshot"]
    assert snapshot["switches"]["1#"]["locked"] is True
    assert snapshot["signals"]["X"]["aspect"] == "open"

    switch_response = client.post(
        "/api/interlocking/switches/operate",
        headers=headers,
        json={"station_id": station_id, "switch_code": "1#", "target_position": "reverse"},
    )
    assert switch_response.status_code == 409
    assert switch_response.json()["detail"] == "道岔已被进路锁闭"

    hostile_response = client.post(
        "/api/interlocking/routes/arrange",
        headers=headers,
        json={"station_id": station_id, "entry_signal": "S", "exit_signal": "IAG"},
    )
    assert hostile_response.status_code == 409
    assert "敌对进路已建立" in hostile_response.json()["detail"]

    occupancy_response = client.post(
        "/api/interlocking/sections/occupancy",
        headers=headers,
        json={"station_id": station_id, "section_code": "IAG", "occupied": True},
    )
    assert occupancy_response.status_code == 200
    occupancy_snapshot = occupancy_response.json()["snapshot"]
    assert occupancy_snapshot["signals"]["X"]["aspect"] == "closed"
    assert "X至I道接车进路" in occupancy_snapshot["locked_routes"]

    cancel_response = client.post(
        "/api/interlocking/routes/cancel",
        headers=headers,
        json={"station_id": station_id, "signal_code": "X"},
    )
    assert cancel_response.status_code == 200
    assert "X至I道接车进路" not in cancel_response.json()["snapshot"]["locked_routes"]
