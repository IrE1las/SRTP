"""Statistics API tests."""

from fastapi.testclient import TestClient

from tests.test_exercise_api import auth_headers, create_x_to_i_exercise


def test_student_and_teacher_statistics(client: TestClient) -> None:
    teacher_headers = auth_headers(client, "teacher_stats", "teacher")
    student_headers = auth_headers(client, "student_stats", "student")
    exercise_id = create_x_to_i_exercise(client, teacher_headers)
    start = client.post("/api/exercise-sessions/start", headers=student_headers, json={"exercise_id": exercise_id})
    session_id = start.json()["session"]["id"]
    client.post(
        "/api/exercise-runtime/routes/arrange",
        headers=student_headers,
        json={"session_id": session_id, "entry_signal": "X", "exit_signal": "I"},
    )

    student_stats = client.get("/api/statistics/student/me", headers=student_headers)
    assert student_stats.status_code == 200
    assert student_stats.json()["total_sessions"] == 1
    assert student_stats.json()["completed_sessions"] == 1

    teacher_stats = client.get("/api/statistics/teacher/overview", headers=teacher_headers)
    assert teacher_stats.status_code == 200
    assert teacher_stats.json()["exercise_count"] == 1
    assert teacher_stats.json()["session_count"] == 1
