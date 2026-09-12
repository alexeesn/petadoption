"""One-off helper: terminate connections to the shared test DB and drop it.

Only used when a previously hung test run left test_pam_db locked.
Safe to delete this file after use.
"""
import os

import os

import psycopg2

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5432"),
    dbname=os.getenv("ADMIN_DB", "postgres"),
    user=os.environ.get("POSTGRES_USER", "pam_user"),
    password=os.environ.get("POSTGRES_PASSWORD", "pam_password"),
)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'test_pam_db' AND pid <> pg_backend_pid()"
    )
    print("terminated connections:", cur.rowcount)
    cur.execute("DROP DATABASE IF EXISTS test_pam_db")
    print("dropped test_pam_db")
conn.close()
