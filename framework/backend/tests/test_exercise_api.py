"""Exercise API acceptance tests."""

from fastapi.testclient import TestClient


def auth_headers(client: TestClient, username: str, role: str) -> dict[str, str]:
    password = "password123"
    if role == "admin":
        from app.core.database import get_db
        from app.core.security import get_password_hash
        from app.models.user import User
        from main import app
        provider = app.dependency_overrides[get_db]()
        db = next(provider)
        db.add(User(username=username, password_hash=get_password_hash(password), role="admin"))
        db.commit()
        provider.close()
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "real_name": username,
            "role": role,
            "student_id": f"{username}-id" if role == "student" else None,
            "class_name": "信号一班" if role == "student" else None,
        },
    )
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_x_to_i_exercise(client: TestClient, teacher_headers: dict[str, str]) -> int:
    response = client.post(
        "/api/exercises",
        headers=teacher_headers,
        json={
            "title": "办理 X 至 I 道接车进路",
            "description": "请在标准站场中办理 X 至 I 道接车进路。",
            "target_routes": [
                {"entry_signal": "X", "exit_signal": "I", "route_name": "X至I道接车进路"}
            ],
            "time_limit": 600,
            "difficulty": "easy",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_teacher_creates_exercise_student_finishes_session(client: TestClient) -> None:
    teacher_headers = auth_headers(client, "teacher_phase4", "teacher")
    student_headers = auth_headers(client, "student_phase4", "student")
    exercise_id = create_x_to_i_exercise(client, teacher_headers)

    lobby_response = client.get("/api/exercises/lobby", headers=student_headers)
    assert lobby_response.status_code == 200
    assert any(item["id"] == exercise_id for item in lobby_response.json())

    start_response = client.post(
        "/api/exercise-sessions/start",
        headers=student_headers,
        json={"exercise_id": exercise_id},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    session_id = start_payload["session"]["id"]
    assert start_payload["session"]["status"] == "ongoing"
    assert start_payload["station_detail"]["station"]["station_code"] == "DOWN_THROAT_STANDARD"

    runtime_response = client.post(
        "/api/exercise-runtime/routes/arrange",
        headers=student_headers,
        json={"session_id": session_id, "entry_signal": "X", "exit_signal": "I"},
    )
    assert runtime_response.status_code == 200
    runtime_payload = runtime_response.json()
    assert runtime_payload["success"] is True
    assert runtime_payload["session"]["status"] == "completed"
    assert runtime_payload["session"]["completion_status"] == "success"
    assert runtime_payload["session"]["total_clicks"] == 1
