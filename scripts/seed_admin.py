#!/usr/bin/env python3
"""Seed the admin account (admin@sentio.app — approval-gated deployment).

Creates/updates the seeded admin so public signups can be approved from
Settings -> User Management. The password is printed once on first create;
re-running only tops up a missing/broken admin row (never resets a password).

Idempotent: safe to run any time.
"""

import hashlib
import secrets
import sys

import psycopg2


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def main() -> int:
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="sentiment",
            user="sentiment", password="sentiment", connect_timeout=3,
        )
    except Exception as exc:
        print(f"  ⏭ postgres not reachable ({exc.__class__.__name__}) — admin seeds on the next run")
        return 0

    with conn, conn.cursor() as cur:
        # make sure the role/status columns exist (pre-migration databases)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'approved'")

        cur.execute("SELECT status FROM users WHERE email = 'admin@sentio.app'")
        row = cur.fetchone()
        if row and row[0] == "approved":
            print("  ✓ admin account already present: admin@sentio.app")
            conn.close()
            return 0

        password = secrets.token_urlsafe(9)
        cur.execute(
            "INSERT INTO users (email, name, password_hash, role, status) "
            "VALUES (%s, %s, %s, 'admin', 'approved') "
            "ON CONFLICT (email) DO UPDATE SET role = 'admin', status = 'approved' "
            "WHERE users.status <> 'approved' OR users.role <> 'admin'",
            ("admin@sentio.app", "Sentio Admin", _hash_password(password)),
        )
        if row is None:
            conn.commit()
            print("  ✓ admin account created: admin@sentio.app")
            print(f"  ✓ admin password (save it now): {password}")
        else:
            # admin existed but was pending/rejected — re-approve, keep old password
            conn.commit()
            print("  ✓ existing admin re-approved: admin@sentio.app")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
