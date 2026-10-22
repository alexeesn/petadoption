import os
import psycopg2

os.environ.setdefault("PGPASSWORD", "pam_password")
conn = psycopg2.connect(
    dbname="pam_db", user="pam_user", password="pam_password",
    host="localhost", port=5432,
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='pam_qa'")
if cur.fetchone():
    print("pam_qa already exists")
else:
    cur.execute("CREATE DATABASE pam_qa")
    print("created pam_qa")
cur.close()
conn.close()
