"""Idempotent setup for the `crack-cms-question-images` Supabase bucket.

Run from the backend dir:

    python scripts/setup_supabase_bucket.py

Safe to re-run; if the bucket already exists, it logs and exits 0.
"""
import os
import sys

BUCKET = "crack-cms-question-images"


def main() -> int:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 1

    from supabase import create_client

    client = create_client(url, key)
    existing = {b.name for b in client.storage.list_buckets()}
    if BUCKET in existing:
        print(f"OK: bucket {BUCKET!r} already exists")
        return 0

    client.storage.create_bucket(BUCKET, options={"public": True})
    print(f"OK: created bucket {BUCKET!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
