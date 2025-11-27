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





# ------------------------------------------------------
# CLEANERS
# ------------------------------------------------------

def clean_text(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = raw
    s = re.sub(r"```(?:.|\n)*?```", "", s)
    s = s.replace("```", "")
    s = s.replace("\\`", "").replace("`", "")
    return s.strip()



# ------------------------------------------------------
# LOAD CANONICAL.MD (Format B)
# ------------------------------------------------------

def load_canonical_md(path: Path):
    """
    Expected pattern:

    ## Canonical 0001
    USER_INTENT: student_monthly_spend
    VALID_CASE: student_missing

    SQL:
    SELECT ...
    """
    txt = path.read_text(encoding="utf-8")
    blocks = re.split(r"^##\s+Canonical", txt, flags=re.MULTILINE)
    out = {}

    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue

        # ID
        m_id = re.match(r"^(\d{4})", blk)
        if not m_id:
            continue
        cid = m_id.group(1)

        # VALID_CASE
        m_case = re.search(r"VALID_CASE:\s*(.+)", blk)
        valid_case = m_case.group(1).strip() if m_case else "student_missing"

        # SQL (still needed for NLV → canonical pairing even though the assistant will NOT output SQL)
        m_sql = re.search(r"SQL:\s*(.*)", blk, flags=re.DOTALL)
        sql = m_sql.group(1).strip() if m_sql else ""

        out[cid] = {
            "valid_case": valid_case,
            "sql": sql
        }

    return out



# ------------------------------------------------------
# LOAD COT REASONING
# ------------------------------------------------------

def load_cot(path: Path):
    """COT file must use same ## Canonical 0001 headers."""
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



# ------------------------------------------------------
# LOAD NLV
# ------------------------------------------------------

def normalize_col(name: str) -> str:
    return re.sub(r"\s+", "_", name.strip()).lower()


def load_nlv_excel(path: Path):
    df = pd.read_excel(path)
    df.columns = [normalize_col(c) for c in df.columns]

    col_map = {}
    for c in ("nlv_text", "text"):
        if c in df.columns:
            col_map["nlv_text"] = c
            break

    for c in ("canonical_id", "canonicalid"):
        if c in df.columns:
            col_map["canonical_id"] = c
            break

    return df, col_map



# ------------------------------------------------------
# LOAD EDGE CASES
# ------------------------------------------------------

def load_edge_cases(path: Path):
    txt = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+EdgeCase", txt, flags=re.MULTILINE)

    out = []
    for blk in blocks:
        if "User:" not in blk:
            continue
        m_user = re.search(r"User:\s*(.+)", blk)
        m_bot = re.search(r"Assistant:\s*(\{.+\})", blk, flags=re.DOTALL)
        if not (m_user and m_bot):
            continue

        out.append({
            "messages": [
                {"role": "system", "content": load_system_prompt()},
                {"role": "user", "content": m_user.group(1).strip()},
                {"role": "assistant", "content": m_bot.group(1).strip()}
            ]
        })
    return out



# ------------------------------------------------------
# LOAD MULTI-TURN
# ------------------------------------------------------

def load_multi_turn(path: Path):
    txt = clean_text(path.read_text(encoding="utf-8"))
    convos = re.split(r"^##\s+MultiTurn", txt, flags=re.MULTILINE)

    out = []
    for c in convos:
        if "User:" not in c:
            continue

        lines = c.strip().splitlines()
        msgs = []
        msgs.append({"role": "system", "content": load_system_prompt()})

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
# SYSTEM PROMPT LOADER
# ------------------------------------------------------

def load_system_prompt():
    return clean_text(SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"))



# ------------------------------------------------------
# BUILD JSONL
# ------------------------------------------------------

def build_jsonl():

    print("Loading system prompt…")
    system_prompt = load_system_prompt()

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

    print(f"Writing → {OUTPUT_JSONL_PATH}")
    OUTPUT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as fout:

        # ----------------------------------------------------------
        # 1. NLV-driven examples
        # ----------------------------------------------------------
        for _, row in nlv_df.iterrows():
            user_msg = str(row[col_map["nlv_text"]]).strip()
            cid = str(row[col_map["canonical_id"]]).zfill(4)

            if cid not in canonical:
                continue

            valid_case = canonical[cid]["valid_case"]

            # Determine assistant output
            if valid_case == "student_missing":
                assistant_payload = {
                    "text": "Which student should I check? Please share their full name.",
                    "rows": None,
                    "html": ""
                }

            elif valid_case == "vendor_missing":
                assistant_payload = {
                    "text": "Which vendor do you want to look at?",
                    "rows": None,
                    "html": ""
                }

            else:  # student_present, vendor_present, month_present, etc.
                assistant_payload = {
                    "text": "",
                    "rows": None,
                    "html": ""
                }

            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)}
                ]
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

        # ----------------------------------------------------------
        # 2. EDGE CASES
        # ----------------------------------------------------------
        for ec in edge_cases:
            fout.write(json.dumps(ec, ensure_ascii=False) + "\n")

        # ----------------------------------------------------------
        # 3. MULTI TURN
        # ----------------------------------------------------------
        for mt in multi_turn:
            fout.write(json.dumps(mt, ensure_ascii=False) + "\n")

    print("✔ DONE – Clean JSONL ready.")



if __name__ == "__main__":
    build_jsonl()