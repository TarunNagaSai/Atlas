"""Backfill bm25_tokens for chunks already in pgvector.

Existing rows were ingested before the BM25 field existed — they carry text +
embedding but an empty ``bm25_tokens`` array. This reads each such row's ``text``
and writes the tokens using the SAME tokenizer used at query time
(``schema.documents.bm25_tokenize``), so the in-memory ``rank_bm25`` index built
from these tokens matches incoming queries exactly.

Prereqs:
  1. Apply migrations/0001_add_bm25_tokens.sql first (adds the column).
  2. DATABASE_URL must be set (.env).

Usage:
  uv run python scripts/backfill_bm25_tokens.py            # backfill empty rows
  uv run python scripts/backfill_bm25_tokens.py --all      # re-tokenize every row
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running a file inside scripts/ puts that dir on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schema.documents import bm25_tokenize
from app.schema.llm_settings import get_settings

BATCH = 500


def main(force_all: bool) -> None:
    import psycopg2
    import psycopg2.extras

    s = get_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot backfill.")

    # Two connections: committing on the same connection as an open named
    # (server-side) cursor invalidates that cursor mid-iteration.
    read_conn = psycopg2.connect(s.database_url)
    write_conn = psycopg2.connect(s.database_url)
    where = "" if force_all else "WHERE bm25_tokens = '{}'"
    with read_conn.cursor(name="backfill_cur") as cur:  # server-side: stream rows
        cur.itersize = BATCH
        cur.execute(f"SELECT id, text FROM chunks {where}")

        updated = 0
        pending: list[tuple[list[str], str]] = []
        for cid, text in cur:
            pending.append((bm25_tokenize(text or ""), cid))
            if len(pending) >= BATCH:
                updated += _flush(write_conn, pending)
                pending.clear()
                print(f"  updated {updated} rows...", flush=True)
        if pending:
            updated += _flush(write_conn, pending)

    read_conn.close()
    write_conn.close()
    print(f"done — backfilled bm25_tokens for {updated} chunk(s).")


def _flush(write_conn, rows: list[tuple[list[str], str]]) -> int:
    import psycopg2.extras

    with write_conn.cursor() as w:
        psycopg2.extras.execute_values(
            w,
            "UPDATE chunks SET bm25_tokens = data.toks::text[] "
            "FROM (VALUES %s) AS data(toks, id) WHERE chunks.id = data.id",
            rows,
        )
    write_conn.commit()
    return len(rows)


if __name__ == "__main__":
    main(force_all="--all" in sys.argv)
