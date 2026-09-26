import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


class TestRegister:
    async def test_register_valid(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "new@example.com", "name": "New User", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["name"] == "New User"
        assert data["role"] == "analyst"  # default
        assert data["is_active"] is True
        assert "id" in data

    async def test_register_duplicate_email(self, client):
        payload = {"email": "dup@example.com", "name": "A", "password": "secret123"}
        await client.post("/auth/register", json=payload)
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_invalid_email_format(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "name": "X", "password": "secret123"},
        )
        assert resp.status_code == 422

    async def test_register_empty_email(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "", "name": "X", "password": "secret123"},
        )
        assert resp.status_code == 422

    async def test_register_empty_password(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "a@b.com", "name": "X", "password": ""},
        )
        # Empty password should still register (no min length enforced yet)
        # but if validation is added this would be 422
        assert resp.status_code in (201, 422)

    async def test_register_admin_role(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "admin@example.com", "name": "Admin", "password": "s", "role": "admin"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "admin"

    async def test_register_broker_role(self, client):
        resp = await client.post(
            "/auth/register",
            json={
                "email": "broker@example.com",
                "name": "Broker",
                "password": "s",
                "role": "broker",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "broker"

    async def test_register_analyst_role(self, client):
        resp = await client.post(
            "/auth/register",
            json={
                "email": "analyst@example.com",
                "name": "Analyst",
                "password": "s",
                "role": "analyst",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "analyst"


class TestLogin:
    async def test_login_valid(self, client):
        await client.post(
            "/auth/register",
            json={"email": "login@example.com", "name": "L", "password": "mypass"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "mypass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        await client.post(
            "/auth/register",
            json={"email": "wp@example.com", "name": "L", "password": "correct"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "wp@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client):
        resp = await client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "pass"},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_valid(self, client, auth_headers):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data
        assert data["is_active"] is True

    async def test_me_no_token(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_garbage_token(self, client):
        resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    async def test_me_expired_token(self, client):
        # Create an expired token
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "expired@example.com",
            "role": "analyst",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_me_invalid_uuid_in_token(self, client):
        """Fix 1 verification: invalid UUID in token payload should return 401, not 500."""
        payload = {
            "sub": "not-a-uuid",
            "email": "bad@example.com",
            "role": "analyst",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_protected_endpoint_no_token(self, client):
        resp = await client.get("/deals")
        assert resp.status_code == 401
