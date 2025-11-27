import json
import re
from pathlib import Path


# ------------------------------------------------------
#  CONFIG: Your actual file paths (Windows)
# ------------------------------------------------------

NLV_MD_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Natural Language Variants\NLV_Data.md"
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
POS_STUDENTS_PATH   = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_students.md")
POS_VENDORS_PATH    = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_vendors.md")
POS_CLINICIANS_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_clinician.md")
POS_INV_DETAIL_PATH = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_invoice_detail.md")
POS_AMBIG_PATH      = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_ambiguous.md")
POS_CHARTS_PATH     = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_charts.md")
POS_PIVOTS_PATH     = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_pivot.md")
POS_DISTRICT_PATH   = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_examples_district.md")
POS_INVOICE_PATH    = Path(r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\Positive Examples\positive_invoice_path.md")


# ------------------------------------------------------
# CLEANING HELPERS
# ------------------------------------------------------

def clean_text(raw: str) -> str:
    """Remove code fences / stray backticks and trim whitespace."""
    if not isinstance(raw, str):
        return ""
    s = raw
    s = re.sub(r"```(?:.|\n)*?```", "", s)  # remove fenced blocks
    s = s.replace("```", "").replace("\\`", "").replace("`", "")
    return s.strip()


# ------------------------------------------------------
# LOADERS
# ------------------------------------------------------

def load_canonical_md(path: Path) -> dict:
    """
    Parse canonical.md of the form:

    ## Canonical 0001

    SELECT ...
    ...
    ## Canonical 0002
    ...

    Returns: { "0001": "<sql>", "0002": "<sql>", ... }
    """
    text = clean_text(path.read_text(encoding="utf-8"))

    # Split on headers like "## Canonical 0001"
    blocks = re.split(r"^##\s+Canonical\s+(\d{4})\s*$", text, flags=re.MULTILINE)

    mapping = {}
    # blocks = ["<preamble>", "0001", "<body1>", "0002", "<body2>", ...]
    for i in range(1, len(blocks), 2):
        cid = blocks[i].strip()
        body = blocks[i + 1].strip()
        if not body:
            continue
        mapping[cid] = body

    print(f"Loaded {len(mapping)} canonical SQL blocks from {path}")
    return mapping


def load_cot_md(path: Path) -> dict:
    """
    Parse CoT_reasoning_Master.md of the form:

    ## Canonical 0001 – Title...
    <reasoning text...>

    Returns: { "0001": "<cot text>", ... }
    """
    text = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+Canonical\s+(\d{4})\b.*$", text, flags=re.MULTILINE)

    mapping = {}
    for i in range(1, len(blocks), 2):
        cid = blocks[i].strip()
        body = blocks[i + 1].strip()
        if not body:
            continue
        mapping[cid] = body

    print(f"Loaded {len(mapping)} CoT reasoning blocks from {path}")
    return mapping


def load_nlv_md(path: Path) -> list:
    """
    Parse NLV_Data.md of the form:

    ## NLV 0001
    NLV Text: ...
    Canonical ID: 0001

    Returns a list of dicts:
      { "nlv_id": "0001", "nlv_text": "...", "canonical_id": "0001" }
    """
    print(f"Loading NLV mappings from {path} …")

    text = clean_text(path.read_text(encoding="utf-8"))
    blocks = re.split(r"^##\s+NLV\s+(\d+)\s*$", text, flags=re.MULTILINE)

    results = []
    for i in range(1, len(blocks), 2):
        nlv_id = blocks[i].strip()
        body = blocks[i + 1]

        m_text = re.search(r"NLV Text:\s*(.+)", body)
        m_canon = re.search(r"Canonical ID:\s*(\d+)", body)

        if not (m_text and m_canon):
            continue

        nlv_text = m_text.group(1).strip()
        canonical_id = m_canon.group(1).strip().zfill(4)

        results.append(
            {
                "nlv_id": nlv_id,
                "nlv_text": nlv_text,
                "canonical_id": canonical_id,
            }
        )

    print(f"  → Loaded {len(results)} NLV entries from markdown")
    return results


def load_edge_cases(path: Path) -> list:
    """
    Parse edge_cases.md of the form: (matches your file)

    ## EdgeCase 0001 – ...
    User: "Show me the hours."
    Assistant_Text: "I need a student name..."
    CoT: "Reasoning..."

    Returns: [
      {
        "messages": [
          {"role": "user", "content": "..."},
          {"role": "assistant", "content": "..."}
        ],
        "cot_reasoning": "..."
      },
      ...
    ]
    """
    print(f"Loading edge cases from {path} …")
    if not path.exists():
        print(f"  ⚠ File not found, skipping: {path}")
        return []

    txt = clean_text(path.read_text(encoding="utf-8"))

    # Split at each EdgeCase header line
    blocks = re.split(r"^##\s+EdgeCase[^\n]*$", txt, flags=re.MULTILINE)
    out = []

    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue

        m_user = re.search(r"User:\s*(.+)", blk)
        m_asst = re.search(r"Assistant_Text:\s*(.+)", blk)
        m_cot  = re.search(r"CoT:\s*(.+)", blk)

        if not (m_user and m_asst):
            continue

        raw_user = m_user.group(1).strip()
        raw_asst = m_asst.group(1).strip()
        raw_cot  = m_cot.group(1).strip() if m_cot else ""

        # Try to decode quoted strings like "Show me the hours."
        def decode_maybe_json(s: str) -> str:
            s = s.strip()
            if s.startswith('"'):
                try:
                    return json.loads(s)
                except Exception:
                    return s.strip('"')
            return s

        user_text = decode_maybe_json(raw_user)
        asst_text = decode_maybe_json(raw_asst)
        cot_text  = decode_maybe_json(raw_cot) if raw_cot else ""

        out.append(
            {
                "messages": [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": asst_text},
                ],
                "cot_reasoning": cot_text,
            }
        )

    print(f"  → Loaded {len(out)} edge-case conversations")
    return out


def load_multi_turn(path: Path) -> list:
    """
    Parse multi_turn_data.md of the form: (matches your file)

    ## MultiTurn 0001 – ...
    Turn1_User: "..."
    Turn1_Assistant_Text: "..."
    Turn1_CoT: "..."

    Turn2_User: "..."
    Turn2_Assistant_Text: "..."
    Turn2_CoT: "..."

    Turn3_User: "..."
    Turn3_Assistant_Output_JSON: "{\"sql\": \"...\"}"
    Turn3_CoT: "..."

    Returns: [
      {
        "messages":[ user, assistant, user, assistant, user, assistant ],
        "cot_reasoning": { "1": "...", "2": "...", "3": "..." }
      },
      ...
    ]
    """
    print(f"Loading multi-turn conversations from {path} …")
    if not path.exists():
        print(f"  ⚠ File not found, skipping: {path}")
        return []

    txt = clean_text(path.read_text(encoding="utf-8"))
    # Split on each MultiTurn header
    convos = re.split(r"^##\s+MultiTurn[^\n]*$", txt, flags=re.MULTILINE)
    out = []

    for blk in convos:
        blk = blk.strip()
        if not blk:
            continue

        lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
        if not lines:
            continue

        messages = []
        cot_by_turn = {}

        def decode_maybe_json(s: str) -> str:
            s = s.strip()
            if s.startswith('"'):
                try:
                    return json.loads(s)
                except Exception:
                    return s.strip('"')
            return s

        for ln in lines:
            # TurnN_User: ...
            m_user = re.match(r"Turn(\d+)_User:\s*(.+)", ln)
            if m_user:
                turn = m_user.group(1)
                raw = m_user.group(2).strip()
                text = decode_maybe_json(raw)
                messages.append({"role": "user", "content": text})
                continue

            # TurnN_Assistant_Text: ...
            m_ast_text = re.match(r"Turn(\d+)_Assistant_Text:\s*(.+)", ln)
            if m_ast_text:
                turn = m_ast_text.group(1)
                raw = m_ast_text.group(2).strip()
                decoded = decode_maybe_json(raw)
                messages.append({"role": "assistant", "content": decoded})
                continue

            # TurnN_Assistant_Output_JSON: "{\"sql\": \"...\"}"
            m_ast_json = re.match(r"Turn(\d+)_Assistant_Output_JSON:\s*(.+)", ln)
            if m_ast_json:
                turn = m_ast_json.group(1)
                raw = m_ast_json.group(2).strip()
                decoded = decode_maybe_json(raw)
                messages.append({"role": "assistant", "content": decoded})
                continue

            # TurnN_CoT: ...
            m_cot = re.match(r"Turn(\d+)_CoT:\s*(.+)", ln)
            if m_cot:
                turn = m_cot.group(1)
                raw_cot = m_cot.group(2).strip()
                cot_by_turn[turn] = decode_maybe_json(raw_cot)
                continue

        if len(messages) >= 2:
            out.append(
                {
                    "messages": messages,
                    "cot_reasoning": cot_by_turn,
                }
            )

    print(f"  → Loaded {len(out)} multi-turn conversations")
    return out


def load_positive_examples(path: Path, example_prefix: str) -> list:
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

    Returns: [ {"user": <user_text>, "assistant": <assistant_json_str>}, ... ]
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
            continue
        user_text = m_user.group(1).strip()

        # --- Extract assistant JSON (brace-balanced) ---
        m_ast = re.search(r"Assistant:\s*(\{)", block)
        if not m_ast:
            continue

        json_start = m_ast.start(1)
        tail = block[json_start:]

        lines = tail.splitlines()
        json_lines = []
        balance = 0
        started = False

        for line in lines:
            if not started:
                if "{" not in line:
                    continue
                started = True

            balance += line.count("{")
            balance -= line.count("}")
            json_lines.append(line)

            if started and balance == 0:
                break

        json_str = "\n".join(json_lines).strip()

        try:
            json.loads(json_str)
        except json.JSONDecodeError:
            print(f"  ⚠ Invalid JSON in {example_prefix} block:")
            preview = "\n".join(json_str.splitlines()[:5])
            print(preview)
            continue

        examples.append({"user": user_text, "assistant": json_str})

    print(f"  → Loaded {len(examples)} {example_prefix} examples from {path}")
    return examples


# ------------------------------------------------------
# MAIN BUILDER
# ------------------------------------------------------

def build_jsonl():
    print("Loading system prompt…")
    system_prompt = clean_text(SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"))

    print("Loading canonical SQL…")
    canonical_sql_map = load_canonical_md(CANONICAL_MD_PATH)

    print("Loading CoT reasoning…")
    cot_map = load_cot_md(COT_MD_PATH)

    print("Loading NLV → Canonical mappings (markdown)…")
    nlv_entries = load_nlv_md(NLV_MD_PATH)

    print("Loading edge cases…")
    edge_cases = load_edge_cases(EDGE_CASES_MD_PATH)

    print("Loading multi-turn dialogs…")
    multi_turn_convos = load_multi_turn(MULTI_TURN_MD_PATH)

    print("Loading ALL positive example files…")
    pos_students   = load_positive_examples(POS_STUDENTS_PATH,   "StudentExample")
    pos_vendors    = load_positive_examples(POS_VENDORS_PATH,    "VendorExample")
    pos_clinicians = load_positive_examples(POS_CLINICIANS_PATH, "ClinicianExample")
    pos_inv_detail = load_positive_examples(POS_INV_DETAIL_PATH, "InvoiceDetailExample")
    pos_ambig      = load_positive_examples(POS_AMBIG_PATH,      "AmbiguousExample")
    pos_charts     = load_positive_examples(POS_CHARTS_PATH,     "ChartExample")
    pos_pivots     = load_positive_examples(POS_PIVOTS_PATH,     "PivotExample")
    pos_district   = load_positive_examples(POS_DISTRICT_PATH,   "DistrictExample")
    pos_invoice    = load_positive_examples(POS_INVOICE_PATH,    "InvoiceExample")

    all_positive = (
        pos_students
        + pos_vendors
        + pos_clinicians
        + pos_inv_detail
        + pos_ambig
        + pos_charts
        + pos_pivots
        + pos_district
        + pos_invoice
    )

    # Make sure output folder exists
    OUTPUT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting → {OUTPUT_JSONL_PATH}\n")

    nlv_count = 0
    edge_count = 0
    multi_count = 0
    pos_count = 0

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as fout:

        # --------------------------------------------------
        # 1) NLV → Canonical (with canonical + CoT as metadata)
        # --------------------------------------------------
        for entry in nlv_entries:
            cid = entry["canonical_id"]
            nlv_text = entry["nlv_text"]

            if cid not in canonical_sql_map:
                print(f"  ⚠ Canonical ID {cid} (NLV {entry['nlv_id']}) not in canonical.md, skipping.")
                continue

            asst_payload = {
                "text": "",
                "rows": None,
                "html": "",
            }

            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": nlv_text},
                    {
                        "role": "assistant",
                        "content": json.dumps(asst_payload, ensure_ascii=False),
                    },
                ],
                # extra metadata (ignored by fine-tune APIs but useful / future-proof)
                "canonical_id": cid,
                "canonical_sql": canonical_sql_map.get(cid, ""),
            }

            cot_text = cot_map.get(cid)
            if cot_text:
                record["cot_reasoning"] = cot_text

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            nlv_count += 1

        # --------------------------------------------------
        # 2) Edge cases
        # --------------------------------------------------
        for ec in edge_cases:
            messages = [{"role": "system", "content": system_prompt}] + ec["messages"]
            record = {"messages": messages}
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            edge_count += 1

        # --------------------------------------------------
        # 3) Multi-turn dialogs
        # --------------------------------------------------
        for mt in multi_turn_convos:
            messages = [{"role": "system", "content": system_prompt}] + mt["messages"]
            record = {"messages": messages}
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            multi_count += 1

        # --------------------------------------------------
        # 4) Positive examples (students, vendors, clinicians, etc.)
        # --------------------------------------------------
        for block in all_positive:
            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": block["user"]},
                    {"role": "assistant", "content": block["assistant"]},
                ]
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            pos_count += 1

    print("✔ DONE – Clean JSONL ready!")
    print(f"   NLV-derived examples:   {nlv_count}")
    print(f"   Edge case examples:     {edge_count}")
    print(f"   Multi-turn examples:    {multi_count}")
    print(f"   Positive examples:      {pos_count}")
    print(f"   TOTAL examples:         {nlv_count + edge_count + multi_count + pos_count}")


# ------------------------------------------------------
# MAIN ENTRY
# ------------------------------------------------------

if __name__ == "__main__":
    build_jsonl()
