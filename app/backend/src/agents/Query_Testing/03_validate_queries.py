import sqlite3
import json
import pandas as pd
import os
import sys

# -----------------------------
# CONFIGURE YOUR PATHS
# -----------------------------
DB_PATH = r"C:\Users\danie\Documents\invoice_agent\invoice.db"
JSONL_PATH = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Query_Testing\query_testing.jsonl"

DISTRICT_KEY = "I51P-DA8D-HJQ0"

# -----------------------------
# SANITY CHECKS
# -----------------------------
if not os.path.exists(DB_PATH):
    print(f"❌ ERROR: SQLite database not found at:\n{DB_PATH}")
    sys.exit(1)

if not os.path.exists(JSONL_PATH):
    print(f"❌ ERROR: JSONL file not found at:\n{JSONL_PATH}")
    sys.exit(1)

print("✔ Database found:", DB_PATH)
print("✔ JSONL found:", JSONL_PATH)

# -----------------------------
# CONNECT TO DATABASE
# -----------------------------
try:
    conn = sqlite3.connect(DB_PATH)
except Exception as e:
    print("❌ ERROR opening SQLite DB:", e)
    sys.exit(1)

print("\n=== Running SQL validation for all questions ===\n")

# -----------------------------
# PROCESS JSONL
# -----------------------------
with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue  # skip empty lines

        try:
            entry = json.loads(line)
        except Exception as e:
            print("\n❌ JSON PARSE ERROR:", e)
            print("Line content:", line)
            continue

        qid = entry.get("id", "UNKNOWN")
        question = entry.get("question", "UNKNOWN")
        sql = entry.get("sql_used")  # do not default to ""

        print("\n---------------------------------------------")
        print(f"ID: {qid}")
        print(f"Question: {question}\n")
        print("SQL:")
        print(sql if sql is not None else "")

        # -----------------------------
        # SKIP ENTRIES WITH NO SQL
        # -----------------------------
        if sql is None or not isinstance(sql, str) or sql.strip() == "":
            print("\n(No SQL to validate — skipping)\n")
            continue

        # -----------------------------
        # Replace placeholder district key
        # -----------------------------
        sql_to_run = sql.replace(":district_key", f"'{DISTRICT_KEY}'")

        # -----------------------------
        # Auto-fill all other parameters with test values
        # -----------------------------
        param_replacements = {
            ":student_name": "'addison johnson'",
            ":service_month": "'august'",
            ":vendor_name": "'action supportive care'"
        }

        for placeholder, fake_value in param_replacements.items():
            sql_to_run = sql_to_run.replace(placeholder, fake_value)

        # -----------------------------
        # EXECUTE SQL
        # -----------------------------
        try:
            df = pd.read_sql_query(sql_to_run, conn)
            print("\nRESULTS:")
            if df.empty:
                print("(No rows returned)")
            else:
                print(df.to_string(index=False))
        except Exception as e:
            print("\n❌ SQL ERROR:")
            print(str(e))

# -----------------------------
# FINISH
# -----------------------------
conn.close()
print("\n=== DONE ===")
