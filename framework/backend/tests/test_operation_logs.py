"""Operation log tests."""

from fastapi.testclient import TestClient

from tests.test_exercise_api import auth_headers, create_x_to_i_exercise


def test_runtime_operations_create_ordered_logs(client: TestClient) -> None:
    teacher_headers = auth_headers(client, "teacher_logs", "teacher")
    student_headers = auth_headers(client, "student_logs", "student")
    exercise_id = create_x_to_i_exercise(client, teacher_headers)
    start_response = client.post(
        "/api/exercise-sessions/start",
        headers=student_headers,
        json={"exercise_id": exercise_id},
    )
    session_id = start_response.json()["session"]["id"]

    switch_response = client.post(
        "/api/exercise-runtime/switches/operate",
        headers=student_headers,
        json={"session_id": session_id, "switch_code": "1#", "target_position": "reverse"},
    )
    assert switch_response.status_code == 200

    route_response = client.post(
        "/api/exercise-runtime/routes/arrange",
        headers=student_headers,
        json={"session_id": session_id, "entry_signal": "S", "exit_signal": "IAG"},
    )
    assert route_response.status_code == 200

    replay_response = client.get(f"/api/exercise-sessions/{session_id}/replay", headers=student_headers)
    assert replay_response.status_code == 200
    logs = replay_response.json()["logs"]
    assert [log["sequence_no"] for log in logs] == [1, 2]
    assert logs[0]["state_before"]
    assert logs[0]["state_after"]
    assert logs[1]["operation_type"] == "select_route"
