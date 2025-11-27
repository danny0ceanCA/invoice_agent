import json
import re
from pathlib import Path
import pandas as pd


# ------------------------------------------------------
#  CONFIG: Your actual file paths (Windows)
# ------------------------------------------------------

NLV_XLSX_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\NLV_Data_Mapping.xlsx"
)

CANONICAL_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Canonical Data\canonical.md"
)

COT_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\CoT_reasoning_Master.md"
)

SCHEMA_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Schema Reference\schema_reference.md"
)

EDGE_CASES_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Edge Cases\edge_cases.md"
)

MULTI_TURN_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Multi-turn Data\multi_turn_data.md"
)

SYSTEM_PROMPT_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\system_prompt.txt"
)

OUTPUT_JSONL_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\cot_finetuning_data.jsonl"
)


# ---- POSITIVE EXAMPLES ----
POS_STUDENTS_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_students.md")
POS_VENDORS_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_vendors.md")
POS_CLINICIANS_PATH = Path( r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_clinician.md")
POS_INV_DETAIL_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_invoice_detail.md")
POS_AMBIG_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_ambiguous.md")
POS_CHARTS_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_charts.md")
POS_PIVOTS_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_pivot.md")
POS_District_Path = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_district.md")
POS_INVOICE_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_invoice_path.md")


# ------------------------------------------------------
# CLEANING HELPERS
# ------------------------------------------------------

def clean_text(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = raw
    s = re.sub(r"```(?:.|\n)*?```", "", s)  # remove fenced blocks
    s = s.replace("```", "").replace("\\`", "").replace("`", "")
    return s.strip()


# ------------------------------------------------------
# LOADERS
# ------------------------------------------------------

def normalize_col(name: str) -> str:
    return re.sub(r"\s+", "_", name.strip()).lower()


def load_nlv_excel(path: Path):
    df = pd.read_excel(path)
    df.columns = [normalize_col(c) for c in df.columns]

    col_map = {}
    for c in ("nlv_text", "text", "nvl_text"):
        if c in df.columns:
            col_map["nlv_text"] = c
            break

    for c in ("canonical_id", "canonical", "canonicalid"):
        if c in df.columns:
            col_map["canonical_id"] = c
            break

    return df, col_map


def load_canonical_md(path: Path) -> dict:
    """
    Reads canonical.md format:

    ## Canonical 0001
    SQL: SELECT ...
    """
    txt = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+Canonical\s+(\d{4})", txt, flags=re.MULTILINE)

    mapping = {}
    # blocks looks like: ["", "0001", "block text", "0002", "block text", ...]

    for i in range(1, len(blocks), 2):
        cid = blocks[i].strip()
        body = blocks[i + 1]

        # extract SQL after "SQL:"
        m_sql = re.search(r"SQL:\s*(.*)", body, re.DOTALL)
        if not m_sql:
            continue

        sql = clean_text(m_sql.group(1))
        mapping[cid] = sql

    return mapping



def load_cot(path: Path) -> dict:
    """
    Expected markdown:

    ## Canonical 0001
    CoT reasoning...
    """
    text = clean_text(path.read_text(encoding="utf-8"))
    lines = text.splitlines()
    out = {}
    current = None
    buf = []

    for line in lines:
        m = re.match(r"^##\s+Canonical\s+(\d{4})", line.strip())
        if m:
            if current and buf:
                out[current] = clean_text("\n".join(buf))
            current = m.group(1)
            buf = []
        else:
            if current:
                buf.append(line)

    if current and buf:
        out[current] = clean_text("\n".join(buf))

    return out



def load_edge_cases(path: Path) -> list:
    txt = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+EdgeCase", txt, flags=re.MULTILINE)
    out = []

    for blk in blocks:
        if "User:" not in blk or "Assistant:" not in blk:
            continue

        m_user = re.search(r"User:\s*(.+)", blk)
        m_assistant = re.search(r"Assistant:\s*(\{[\s\S]+?\})", blk)

        if not (m_user and m_assistant):
            continue

        try:
            assistant_json = json.loads(m_assistant.group(1))
        except:
            print("⚠ Invalid JSON in EdgeCase block:")
            print(m_assistant.group(1))
            continue

        out.append({
            "messages": [
                {"role": "user", "content": m_user.group(1).strip()},
                {"role": "assistant", "content": json.dumps(assistant_json, ensure_ascii=False)}
            ]
        })

    return out



def load_multi_turn(path: Path) -> list:
    txt = clean_text(path.read_text())
    convos = re.split(r"^##\s+MultiTurn", txt, flags=re.MULTILINE)
    out = []

    for blk in convos:
        if "User:" not in blk:
            continue

        lines = blk.strip().splitlines()
        msgs = []

        for ln in lines:
            if ln.startswith("User:"):
                msgs.append({"role": "user", "content": ln.replace("User:", "").strip()})
            elif ln.startswith("Assistant:"):
                payload = ln.replace("Assistant:", "").strip()
                msgs.append({"role": "assistant", "content": payload})

        if len(msgs) >= 2:
            out.append({"messages": msgs})

    return out



# ------------------------------------------------------
#  NEW: UNIVERSAL POSITIVE-EXAMPLE PARSER (robust)
# ------------------------------------------------------

def load_positive_examples(path: Path, example_prefix: str):
    """
    Parse a markdown file containing blocks like:

    ## StudentExample 0001
    User: Show monthly spend for Jack Garcia.
    Assistant:
    {
      "text": "...",
      "rows": [...],
      "html": "..."
    }

    or

    ### VendorExample 0001
    ...

    Returns a list of dicts: {"user": <user_text>, "assistant": <assistant_json_str>}
    """
    print(f"Loading positive examples from {path} ({example_prefix})…")

    if not path.exists():
        print(f"  ⚠ File not found, skipping: {path}")
        return []

    text = path.read_text(encoding="utf-8")

    # Match headings like: ## VendorExample 0001  OR  ### StudentExample 0003
    header_re = re.compile(
        rf"^#+\s+{re.escape(example_prefix)}\s+\d+\s*$",
        re.MULTILINE,
    )
    header_matches = list(header_re.finditer(text))

    if not header_matches:
        print(f"  ⚠ No blocks found for {example_prefix} in {path}")
        return []

    examples = []

    for i, header_match in enumerate(header_matches):
        start = header_match.end()
        end = header_matches[i + 1].start() if i + 1 < len(header_matches) else len(text)
        block = text[start:end]

        # --- Extract user text ---
        m_user = re.search(r"User:\s*(.+)", block)
        if not m_user:
            # No user line, skip this block
            continue
        user_text = m_user.group(1).strip()

        # --- Extract assistant JSON (brace-balanced) ---
        m_ast = re.search(r"Assistant:\s*(\{)", block)
        if not m_ast:
            # No assistant JSON, skip
            continue

        # Start from the first '{' after "Assistant:"
        json_start = m_ast.start(1)
        tail = block[json_start:]

        lines = tail.splitlines()
        json_lines = []
        balance = 0
        started = False

        for line in lines:
            # Wait until we actually see the first '{'
            if not started:
                if "{" not in line:
                    continue
                started = True

            balance += line.count("{")
            balance -= line.count("}")
            json_lines.append(line)

            # When balance returns to 0, we've closed the top-level object
            if started and balance == 0:
                break

        json_str = "\n".join(json_lines).strip()

        # Validate that what we captured is valid JSON
        try:
            json.loads(json_str)
        except json.JSONDecodeError:
            print(f"⚠ Invalid JSON in {example_prefix} block:")
            # Print only the first few lines as a preview
            preview = "\n".join(json_str.splitlines()[:5])
            print(preview)
            continue

        examples.append(
            {
                "user": user_text,
                "assistant": json_str,
            }
        )

    print(f"  → Loaded {len(examples)} {example_prefix} examples from {path}")
    return examples


# ------------------------------------------------------
# MAIN BUILDER
# ------------------------------------------------------

def build_jsonl():

    print("Loading system prompt…")
    system_prompt = clean_text(SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"))

    print("Loading canonical.md…")
    canonical = load_canonical_md(CANONICAL_MD_PATH)

    print("Loading NLV Excel…")
    nlv_df, col_map = load_nlv_excel(NLV_XLSX_PATH)

    print("Loading CoT reasoning…")
    cot_map = load_cot(COT_MD_PATH)

    print("Loading edge cases…")
    edge_cases = load_edge_cases(EDGE_CASES_MD_PATH)

    print("Loading multi-turn…")
    multi_turn = load_multi_turn(MULTI_TURN_MD_PATH)

    print("Loading ALL positive example files…")
    pos_students   = load_positive_examples(POS_STUDENTS_PATH,   "StudentExample")
    pos_vendors    = load_positive_examples(POS_VENDORS_PATH,    "VendorExample")
    pos_clinicians = load_positive_examples(POS_CLINICIANS_PATH, "ClinicianExample")
    pos_invoices   = load_positive_examples(POS_INVOICE_PATH,    "InvoiceDetailExample")

    # Make sure output folder exists
    OUTPUT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing → {OUTPUT_JSONL_PATH}")

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as fout:

        # ------------------------------
        # NLV → Canonical + CoT
        # ------------------------------
        for _, row in nlv_df.iterrows():
            user_msg = row[col_map["nlv_text"]]
            cid = str(row[col_map["canonical_id"]]).zfill(4)

            if cid not in canonical:
                continue

            asst_payload = {"text": "", "rows": None, "html": ""}

            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": json.dumps(asst_payload, ensure_ascii=False)}
                ]
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

        # ------------------------------
        # Edge cases
        # ------------------------------
        for ec in edge_cases:
            fout.write(json.dumps(ec, ensure_ascii=False) + "\n")

        # ------------------------------
        # Multi-turn
        # ------------------------------
        for mt in multi_turn:
            fout.write(json.dumps(mt, ensure_ascii=False) + "\n")

        # ------------------------------
        # Positive examples
        # ------------------------------
        for block in (pos_students + pos_vendors + pos_clinicians + pos_invoices):
            fout.write(json.dumps(block, ensure_ascii=False) + "\n")

    print("✔ DONE – Clean JSONL ready!")


# ------------------------------------------------------
# MAIN ENTRY
# ------------------------------------------------------

if __name__ == "__main__":
    build_jsonl()