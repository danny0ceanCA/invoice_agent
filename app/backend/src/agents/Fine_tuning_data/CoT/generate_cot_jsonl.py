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

CANONICAL_JSONL_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Canonical Data\canonical_query_testing_results.jsonl"
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
# CLEANING HELPERS
# ------------------------------------------------------

def clean_text(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = raw
    # remove code fences
    s = re.sub(r"```(?:.|\n)*?```", "", s)
    s = s.replace("```", "")
    s = s.replace("\\`", "")
    s = s.replace("`", "")
    s = re.sub(r"(?m)^\s*sql\s*$", "", s)
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


def load_canonical_jsonl(path: Path) -> dict:
    mapping = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            cid = str(rec["id"]).zfill(4)
            sql = clean_text(rec.get("sql_used") or rec.get("sql"))
            mapping[cid] = sql
    return mapping


def load_cot(path: Path) -> dict:
    """
    Expected markdown format:

    ## Canonical 0001
    reasoning...
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
    """Expected format:

    ## EdgeCase 0001
    User: ...
    Assistant: {"text": "...", "rows": null, "html": ""}

    """
    txt = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+EdgeCase", txt, flags=re.MULTILINE)
    out = []

    for blk in blocks:
        if "User:" not in blk:
            continue

        m_user = re.search(r"User:\s*(.+)", blk)
        m_assistant = re.search(r"Assistant:\s*(\{.+\})", blk, re.DOTALL)

        if not (m_user and m_assistant):
            continue

        out.append({
            "messages": [
                {"role": "user", "content": m_user.group(1).strip()},
                {"role": "assistant", "content": m_assistant.group(1).strip()}
            ]
        })

    return out


def load_multi_turn(path: Path) -> list:
    """Expected format:

    ## MultiTurn 0001
    User: ...
    Assistant: {...}
    User: ...
    Assistant: {...}
    """
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
# MAIN BUILDER
# ------------------------------------------------------

def build_jsonl():

    print("Loading system prompt...")
    system_prompt = clean_text(Path(SYSTEM_PROMPT_PATH).read_text(encoding="utf-8"))

    print("Loading canonical SQL...")
    canonical = load_canonical_jsonl(CANONICAL_JSONL_PATH)

    print("Loading NLV Excel...")
    nlv_df, col_map = load_nlv_excel(NLV_XLSX_PATH)

    print("Loading CoT reasoning...")
    cot_map = load_cot(COT_MD_PATH)

    print("Loading edge cases...")
    edge_cases = load_edge_cases(EDGE_CASES_MD_PATH)

    print("Loading multi-turn...")
    multi_turn = load_multi_turn(MULTI_TURN_MD_PATH)

    print(f"Writing → {OUTPUT_JSONL_PATH}")
    OUTPUT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as fout:

        # -----------------------
        # NLV → Canonical + CoT
        # -----------------------
        for _, row in nlv_df.iterrows():
            user_msg = row[col_map["nlv_text"]]
            cid = str(row[col_map["canonical_id"]]).zfill(4)

            if cid not in canonical or cid not in cot_map:
                continue

            sql = canonical[cid]

            assistant_payload = {
                "text": "",
                "rows": None,
                "html": "",
                "sql": sql
            }

            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)}
                ]
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

        # -----------------------
        # EDGE CASES
        # -----------------------
        for ec in edge_cases:
            fout.write(json.dumps(ec, ensure_ascii=False) + "\n")

        # -----------------------
        # MULTI TURN
        # -----------------------
        for mt in multi_turn:
            fout.write(json.dumps(mt, ensure_ascii=False) + "\n")

    print("✔ DONE – Clean JSONL ready.")



if __name__ == "__main__":
    build_jsonl()