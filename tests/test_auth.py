"""Auth + admin tests: signup -> pending -> admin approve -> login -> token.

Runs against the live database (skips when PostgreSQL is unreachable, same
as the rest of the suite). Uses a dedicated test email and cleans up after.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("PG_HOST", "localhost")

import pytest  # noqa: E402

from tests.test_api import client, requires_db  # noqa: E402

from api.main import TOKENS  # noqa: E402

TEST_EMAIL = "auth-test@sentio.app"
TEST_ADMIN_EMAIL = "auth-test-admin@sentio.app"
TEST_PASSWORD = "secret123"


def _cleanup():
    import psycopg2

    try:
        conn = psycopg2.connect(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            dbname=os.getenv("PG_DB", "sentiment"),
            user=os.getenv("PG_USER", "sentiment"),
            password=os.getenv("PG_PASSWORD", "sentiment"),
            connect_timeout=3,
        )
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email IN (%s, %s)", (TEST_EMAIL, TEST_ADMIN_EMAIL))
        conn.close()
    except Exception:
        pass
    for token in [t for t, s in TOKENS.items() if s["email"] in (TEST_EMAIL, TEST_ADMIN_EMAIL)]:
        TOKENS.pop(token, None)


def _seed_admin() -> str:
    """Insert a dedicated approved admin with a known password (the seeded
    admin@sentio.app has a random password) -> login -> return its token."""
    import psycopg2

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api.main import _hash_password

    conn = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "sentiment"),
        user=os.getenv("PG_USER", "sentiment"),
        password=os.getenv("PG_PASSWORD", "sentiment"),
        connect_timeout=3,
    )
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, name, password_hash, role, status)
            VALUES (%s, %s, %s, 'admin', 'approved')
            ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash, role = 'admin', status = 'approved'
            """,
            (TEST_ADMIN_EMAIL, "Auth Test Admin", _hash_password(TEST_PASSWORD)),
        )
    conn.close()
    res = client.post("/api/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_PASSWORD})
    body = res.json()
    assert body["status"] == "ok", body
    assert body["role"] == "admin"
    return body["token"]


@requires_db
def test_signup_starts_pending():
    _cleanup()
    res = client.post(
        "/api/signup",
        json={"name": "Auth Test", "email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    body = res.json()
    assert body["status"] == "pending"
    assert "token" not in body


@requires_db
def test_pending_user_cannot_login():
    res = client.post("/api/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    body = res.json()
    assert body["status"] == "pending"
    assert "token" not in body


@requires_db
def test_admin_endpoints_require_auth():
    res = client.get("/api/admin/users")
    assert res.status_code == 401
    res = client.post("/api/admin/users/approve", json={"email": TEST_EMAIL})
    assert res.status_code == 401


@requires_db
def test_full_approval_flow():
    admin_token = _seed_admin()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # pending list contains the signup
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 200
    emails = [u["email"] for u in res.json()["users"]]
    assert TEST_EMAIL in emails

    # approve -> login works and returns a token
    res = client.post("/api/admin/users/approve", json={"email": TEST_EMAIL}, headers=headers)
    assert res.status_code == 200
    res = client.post("/api/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    body = res.json()
    assert body["status"] == "ok"
    token = body["token"]
    assert token

    # token gates the analyze endpoint: no token -> 401, wrong-user token -> 403
    res = client.post("/api/stream/live", json={"minutes": 0.5, "rate": 5})
    assert res.status_code == 401
    res = client.post(
        "/api/stream/live",
        json={"minutes": 0.5, "rate": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    client.post("/api/stream/stop", headers={"Authorization": f"Bearer {token}"})

    # non-admin token cannot use admin endpoints
    res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


@requires_db
def test_reject_flow_blocks_login():
    admin_token = _seed_admin()
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/admin/users/reject", json={"email": TEST_EMAIL}, headers=headers)
    assert res.status_code == 200
    res = client.post("/api/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert res.json()["status"] == "error"


@requires_db
def test_delete_flow_allows_resignup():
    admin_token = _seed_admin()
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/admin/users/delete", json={"email": TEST_EMAIL}, headers=headers)
    assert res.status_code == 200
    # the email is free again -> signup succeeds as pending
    res = client.post(
        "/api/signup",
        json={"name": "Auth Test", "email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert res.json()["status"] == "pending"
    _cleanup()
