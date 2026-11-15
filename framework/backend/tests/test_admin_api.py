"""Admin API tests."""

from fastapi.testclient import TestClient

from tests.test_exercise_api import auth_headers


def test_admin_can_manage_users_and_non_admin_is_rejected(client: TestClient) -> None:
    admin_headers = auth_headers(client, "admin_final", "admin")
    student_headers = auth_headers(client, "student_admin_reject", "student")

    forbidden = client.get("/api/admin/overview", headers=student_headers)
    assert forbidden.status_code == 403

    overview = client.get("/api/admin/overview", headers=admin_headers)
    assert overview.status_code == 200
    assert overview.json()["user_count"] >= 2

    users = client.get("/api/admin/users", headers=admin_headers)
    assert users.status_code == 200
    target = next(user for user in users.json() if user["username"] == "student_admin_reject")

    updated = client.put(
        f"/api/admin/users/{target['id']}",
        headers=admin_headers,
        json={"real_name": "已修改学生", "role": "student", "class_name": "信号二班"},
    )
    assert updated.status_code == 200
    assert updated.json()["real_name"] == "已修改学生"
