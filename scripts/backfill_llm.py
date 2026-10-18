#!/usr/bin/env python3
"""Backfill llm_label/llm_score for legacy comments rows (batched, idempotent).

Scores rows where llm_label IS NULL with the cardiffnlp tweet-RoBERTa used by the
Spark stream, so every headline metric can be LLM-only. Safe to re-run: it skips
already-scored rows and resumes until the table is fully scored.

Usage:
    .venv/bin/python scripts/backfill_llm.py            # full backfill
    .venv/bin/python scripts/backfill_llm.py --limit 5000
"""

import argparse
import os
import sys
import time

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spark"))

PG_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "dbname": os.getenv("PG_DB", "sentiment"),
    "user": os.getenv("PG_USER", "sentiment"),
    "password": os.getenv("PG_PASSWORD", "sentiment"),
}

BATCH = 256


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill llm_label for legacy rows.")
    parser.add_argument("--limit", type=int, default=None, help="max rows to score this run")
    args = parser.parse_args()

    from nlp import llm_analyze  # loads the cardiffnlp pipeline once

    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT count(*) AS n FROM comments WHERE llm_label IS NULL")
    remaining = cur.fetchone()["n"]
    print(f"{remaining} rows need llm scoring", flush=True)
    if args.limit:
        remaining = min(remaining, args.limit)

    scored, started = 0, time.time()
    while scored < remaining:
        size = min(BATCH, remaining - scored)
        cur.execute(
            """
            SELECT id, coalesce(cleaned_text, text) AS body
            FROM comments WHERE llm_label IS NULL
            ORDER BY ts DESC NULLS LAST
            LIMIT %s
            """,
            (size,),
        )
        rows = cur.fetchall()
        if not rows:
            break

        updates = []
        for row in rows:
            try:
                result = llm_analyze(row["body"] or "")
                updates.append((result["llm_label"], result["llm_score"], row["id"]))
            except Exception:
                # keep null so a later run can retry, but don't loop forever on the same rows
                updates.append((None, None, row["id"]))

        psycopg2.extras.execute_values(
            cur,
            """
            UPDATE comments AS c SET llm_label = data.llm_label, llm_score = data.llm_score
            FROM (VALUES %s) AS data (llm_label, llm_score, id)
            WHERE c.id = data.id
            """,
            updates,
        )
        conn.commit()
        scored += len(rows)
        rate = scored / max(time.time() - started, 1)
        eta = (remaining - scored) / max(rate, 1) / 60
        print(f"scored {scored}/{remaining} ({rate:.0f}/s, eta {eta:.1f} min)", flush=True)

    cur.close()
    conn.close()
    print("Backfill complete.", flush=True)


if __name__ == "__main__":
    main()
