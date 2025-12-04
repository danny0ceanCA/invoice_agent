import json
import re

INPUT_PATH = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Canonical Data\canonical_query_testing_results.jsonl"
OUTPUT_PATH = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\canonical_postgres.jsonl"

def convert_sqlite_to_postgres(sql: str) -> str:
    """
    Converts SQLite syntax to PostgreSQL syntax using pattern replacement.
    """

    # --- YEAR extraction ---
    sql = re.sub(
        r"strftime\('%Y',\s*invoice_date\)",
        r"EXTRACT(YEAR FROM invoice_date)",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"strftime\('%Y','now'\)",
        r"EXTRACT(YEAR FROM CURRENT_DATE)",
        sql,
        flags=re.IGNORECASE,
    )

    # --- MONTH extraction ---
    sql = re.sub(
        r"strftime\('%m',\s*i\.invoice_date\)",
        r"EXTRACT(MONTH FROM i.invoice_date)",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"strftime\('%m',\s*invoice_date\)",
        r"EXTRACT(MONTH FROM invoice_date)",
        sql,
        flags=re.IGNORECASE,
    )

    # --- YEAR-MONTH extraction ---
    sql = re.sub(
        r"strftime\('%Y-%m',\s*i\.invoice_date\)",
        r"TO_CHAR(i.invoice_date, 'YYYY-MM')",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"strftime\('%Y-%m',\s*invoice_date\)",
        r"TO_CHAR(invoice_date, 'YYYY-MM')",
        sql,
        flags=re.IGNORECASE,
    )

    # --- date(invoice_date) → invoice_date::date ---
    sql = re.sub(
        r"\bdate\(\s*i?\.?invoice_date\s*\)",
        r"invoice_date::date",
        sql,
        flags=re.IGNORECASE,
    )

    # --- date('now', '-X months') ---
    sql = re.sub(
        r"date\('now',\s*'-(\d+)\s*months?'\)",
        r"CURRENT_DATE - INTERVAL '\1 months'",
        sql,
        flags=re.IGNORECASE,
    )

    # --- School-year start logic ---
    sql = sql.replace(
        "date(strftime('%Y','now')||'-07-01')",
        "make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 7, 1)"
    )

    sql = sql.replace(
        "date(strftime('%Y','now')||'-06-30','+1 year')",
        "make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int + 1, 6, 30)"
    )

    # Cleanup double spaces, formatting
    sql = re.sub(r"\s+", " ", sql).strip()

    return sql


def migrate_canonical_file():
    print("Loading canonical JSONL…")

    with open(INPUT_PATH, "r", encoding="utf-8") as infile, \
         open(OUTPUT_PATH, "w", encoding="utf-8") as outfile:

        for line in infile:
            if not line.strip():
                continue

            record = json.loads(line)

            original_sql = record.get("sql_used", "")
            new_sql = convert_sqlite_to_postgres(original_sql)

            record["sql_used"] = new_sql

            outfile.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Migration complete! Output written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    migrate_canonical_file()
