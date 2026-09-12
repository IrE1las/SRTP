"""AI scoring tests."""

from fastapi.testclient import TestClient

from tests.test_exercise_api import auth_headers, create_x_to_i_exercise


def test_ai_score_generated_after_session_completion(client: TestClient) -> None:
    teacher_headers = auth_headers(client, "teacher_ai", "teacher")
    student_headers = auth_headers(client, "student_ai", "student")
    exercise_id = create_x_to_i_exercise(client, teacher_headers)
    start = client.post("/api/exercise-sessions/start", headers=student_headers, json={"exercise_id": exercise_id})
    session_id = start.json()["session"]["id"]

    client.post(
        "/api/exercise-runtime/routes/arrange",
        headers=student_headers,
        json={"session_id": session_id, "entry_signal": "X", "exit_signal": "I"},
    )

    score_response = client.get(f"/api/ai-scores/sessions/{session_id}", headers=student_headers)
    assert score_response.status_code == 200
    score = score_response.json()
    assert score["total_score"] > 0
    assert score["deepseek_response"]["mode"] in ["local_fallback", "deepseek_placeholder"]
