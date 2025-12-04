import json
import pandas as pd
from pathlib import Path

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
SYSTEM_PROMPT_PATH = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\system_prompt.txt"
CANONICAL_JSON_PATH = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\canonical_query_testing_results.jsonl"
EXCEL_FILE = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\NLV_Data_Mapping.xlsx"
OUTPUT_JSONL = r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\nlv_training_output.jsonl"

# Column names in Excel
NLV_COLUMN = "NLV Text"
ID_COLUMN = "Canonical_ID"
NLV_ID_COLUMN = "NLV ID"

# ------------------------------------------------------------
# Load system prompt
# ------------------------------------------------------------
print("Loading system prompt…")
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

# ------------------------------------------------------------
# Load canonical JSONL as dictionary
# ------------------------------------------------------------
print("Loading canonical data…")

canonical_map = {}  # id → canonical record

with open(CANONICAL_JSON_PATH, "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        canonical_map[str(entry["id"]).zfill(4)] = entry

# ------------------------------------------------------------
# Load Excel file (force full sheet as STRINGS)
# ------------------------------------------------------------
print("Loading Excel file…")
df = pd.read_excel(EXCEL_FILE, dtype=str)

# Clean all strings
df = df.fillna("")

# ------------------------------------------------------------
# Build JSONL training pairs
# ------------------------------------------------------------
output_rows = []

for idx, row in df.iterrows():
    nlv_text = row[NLV_COLUMN].strip()
    nlv_id = str(row[NLV_ID_COLUMN]).strip()

    raw_canonical_id = str(row[ID_COLUMN]).strip()
    canonical_id = raw_canonical_id.zfill(4)  # <-- GUARANTEE "0001" format

    # Lookup canonical
    if canonical_id not in canonical_map:
        print(f"⚠ WARNING: canonical_id '{canonical_id}' not found. Skipping.")
        continue

    canonical = canonical_map[canonical_id]

    # Build training example
    output_rows.append({
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nlv_text},
            {"role": "assistant", "content": json.dumps(canonical)}
        ]
    })

# ------------------------------------------------------------
# Write JSONL output
# ------------------------------------------------------------
print(f"Writing output → {OUTPUT_JSONL}")
with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
    for row in output_rows:
        f.write(json.dumps(row) + "\n")

print(f"✨ Done! {len(output_rows)} training pairs generated.")
