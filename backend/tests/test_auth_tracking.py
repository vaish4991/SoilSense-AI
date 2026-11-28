"""Tests for SQLite user & login tracking endpoints."""
from fastapi.testclient import TestClient

from backend.main import app


def test_auth_register_login_google_and_tracking(tmp_path, monkeypatch):
    db_file = tmp_path / "test_auth.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(db_file))

    with TestClient(app) as client:
        # 1. Register email user
        res = client.post(
            "/api/auth/register",
            json={"email": "alice@example.com", "password": "secret123", "display_name": "Alice"},
        )
        assert res.status_code == 200
        assert res.json()["user"]["email"] == "alice@example.com"
        assert res.json()["user"]["authProvider"] == "email"

        # 2. Duplicate registration fails
        dup = client.post(
            "/api/auth/register",
            json={"email": "alice@example.com", "password": "secret123"},
        )
        assert dup.status_code == 409

        # 3. Wrong password fails
        bad = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "wrong"},
        )
        assert bad.status_code == 401

        # 4. Valid login increments count
        ok = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "secret123"},
        )
        assert ok.status_code == 200
        assert ok.json()["user"]["loginCount"] == 2

        # 5. Google login creates & tracks user
        g1 = client.post(
            "/api/auth/google",
            json={"email": "vaishnavi@gmail.com", "display_name": "Vaishnavi"},
        )
        assert g1.status_code == 200
        assert g1.json()["user"]["authProvider"] == "google"
        assert g1.json()["user"]["loginCount"] == 1

        # 6. Users & login events endpoints return persisted data
        users_res = client.get("/api/auth/users")
        assert users_res.status_code == 200
        assert users_res.json()["total"] == 2

        logins_res = client.get("/api/auth/logins")
        assert logins_res.status_code == 200
        assert logins_res.json()["total"] == 3
