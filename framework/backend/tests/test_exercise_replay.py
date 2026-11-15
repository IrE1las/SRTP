"""Exercise replay tests."""

from fastapi.testclient import TestClient

from tests.test_exercise_api import auth_headers, create_x_to_i_exercise


def test_history_and_replay_return_complete_log_sequence(client: TestClient) -> None:
    teacher_headers = auth_headers(client, "teacher_replay", "teacher")
    student_headers = auth_headers(client, "student_replay", "student")
    exercise_id = create_x_to_i_exercise(client, teacher_headers)
    start_response = client.post(
        "/api/exercise-sessions/start",
        headers=student_headers,
        json={"exercise_id": exercise_id},
    )
    session_id = start_response.json()["session"]["id"]

    client.post(
        "/api/exercise-runtime/routes/arrange",
        headers=student_headers,
        json={"session_id": session_id, "entry_signal": "X", "exit_signal": "I"},
    )

    history_response = client.get("/api/exercise-sessions/history", headers=student_headers)
    assert history_response.status_code == 200
    assert any(item["id"] == session_id for item in history_response.json())

    replay_response = client.get(f"/api/exercise-sessions/{session_id}/replay", headers=student_headers)
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["session"]["id"] == session_id
    assert replay["exercise"]["id"] == exercise_id
    assert len(replay["logs"]) == 1
    assert replay["logs"][0]["state_after"]["signals"]["X"]["aspect"] == "open"
