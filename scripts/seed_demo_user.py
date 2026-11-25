#!/usr/bin/env python3
"""Seed the demo login user (ada@sentio.app / secret123).

Cross-platform replacement for the inline heredoc in bootstrap.sh — works on
Linux, macOS and Windows. Idempotent: safe to run any time.
"""

import hashlib
import secrets
import sys

import os

import psycopg2


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def main() -> int:
    try:
        conn = psycopg2.connect(
            host=os.getenv("PG_HOST", "localhost"), port=int(os.getenv("PG_PORT", "5432")),
            dbname=os.getenv("PG_DB", "sentiment"), user=os.getenv("PG_USER", "sentiment"),
            password=os.getenv("PG_PASSWORD", "sentiment"), connect_timeout=3,
        )
    except Exception as exc:
        print(f"  ⏭ postgres not reachable ({exc.__class__.__name__}) — user seeds on the next run")
        return 0

    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM users WHERE email = 'ada@sentio.app'")
        exists = cur.fetchone()[0] == 1
    if exists:
        print("  ✓ demo login user already present")
        conn.close()
        return 0
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) "
            "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash",
            ("ada@sentio.app", "Ada", _hash_password("secret123")),
        )
    conn.close()
    print("  ✓ demo login ready: ada@sentio.app / secret123")
    return 0


if __name__ == "__main__":
    sys.exit(main())
