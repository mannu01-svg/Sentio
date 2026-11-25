#!/usr/bin/env python3
"""Seed the default admin account: admin@sentio.app / admin123.

The default login ALWAYS works — every start.sh runs this, and the seed
verifies the stored password, repairing it (and the role/status) whenever
the admin row is missing, was left pending/rejected, or had its password
changed. ADMIN_PASSWORD env overrides the default (CI demos: repo secret).

Idempotent: safe to run any time.
"""

import hashlib
import hmac
import os
import secrets
import sys

import psycopg2

DEFAULT_ADMIN_EMAIL = "admin@sentio.app"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, hexdigest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(digest.hex(), hexdigest)
    except (ValueError, AttributeError):
        return False


def main() -> int:
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="sentiment",
            user="sentiment", password="sentiment", connect_timeout=3,
        )
    except Exception as exc:
        print(f"  ⏭ postgres not reachable ({exc.__class__.__name__}) — admin seeds on the next run")
        return 0

    password = os.getenv("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD

    with conn, conn.cursor() as cur:
        # make sure the role/status columns exist (pre-migration databases)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'approved'")

        cur.execute(
            "SELECT password_hash, role, status FROM users WHERE email = %s",
            (DEFAULT_ADMIN_EMAIL,),
        )
        row = cur.fetchone()
        password_hash, role, status = row if row else (None, None, None)
        healthy = (
            row is not None
            and role == "admin"
            and status == "approved"
            and _verify_password(password, password_hash)
        )
        if healthy:
            print(f"  ✓ admin login ready: {DEFAULT_ADMIN_EMAIL} / {'(from ADMIN_PASSWORD env)' if os.getenv('ADMIN_PASSWORD') else DEFAULT_ADMIN_PASSWORD}")
            return 0

        # missing / wrong password / pending / demoted — repair the row so the
        # default login always works after every start.sh
        cur.execute(
            "INSERT INTO users (email, name, password_hash, role, status) "
            "VALUES (%s, %s, %s, 'admin', 'approved') "
            "ON CONFLICT (email) DO UPDATE SET "
            "password_hash = EXCLUDED.password_hash, role = 'admin', status = 'approved'",
            (DEFAULT_ADMIN_EMAIL, "Sentio Admin", _hash_password(password)),
        )
        conn.commit()
        if row is None:
            print(f"  ✓ admin account created: {DEFAULT_ADMIN_EMAIL}")
        else:
            print(f"  ✓ admin login repaired (was missing/pending/wrong password): {DEFAULT_ADMIN_EMAIL}")
        if os.getenv("ADMIN_PASSWORD"):
            print("  ✓ admin password: from ADMIN_PASSWORD env")
        else:
            print(f"  ✓ admin password: {DEFAULT_ADMIN_PASSWORD}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
