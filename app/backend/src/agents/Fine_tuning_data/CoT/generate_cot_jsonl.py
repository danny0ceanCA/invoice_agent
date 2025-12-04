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


def decode_maybe_json_string(s: str) -> str:
    """
    Many of your MD fields look like `"text here"`.
    Try json.loads first; if that fails, strip outer quotes.
    """
    s = s.strip()
    if not s:
        return s
    if s[0] in ('"', "'") and s[-1] == s[0]:
        try:
            return json.loads(s)
        except Exception:
            return s[1:-1].strip()
    return s


# ------------------------------------------------------
# SQL → SCHEMA → SYNTHETIC PAYLOAD HELPERS
# ------------------------------------------------------

def extract_select_columns(canonical_sql: str) -> list:
    """
    Very simple parser to pull column aliases from the SELECT clause.

    Example:
      SELECT LOWER(service_month) AS service_month,
             SUM(total_cost) AS total_cost
      FROM ...

    → ["service_month", "total_cost"]
    """
    if not canonical_sql:
        return []

    m = re.search(r"select\s+(.*?)\s+from", canonical_sql, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return []

    select_body = m.group(1)
    parts = [p.strip() for p in select_body.split(",") if p.strip()]

    cols = []
    for part in parts:
        # Look for "AS alias"
        m_alias = re.search(r"\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*)", part, flags=re.IGNORECASE)
        if m_alias:
            col_name = m_alias.group(1)
        else:
            # Fallback: last token (strip functions)
            tokens = re.split(r"[\s\.]+", part)
            token = tokens[-1] if tokens else "col"
            col_name = re.sub(r"[^a-zA-Z0-9_]", "", token) or "col"
        cols.append(col_name)
    return cols


def fake_value_for_column(col_name: str, row_idx: int):
    """
    Heuristics to generate plausible synthetic values based on column name.
    """
    name = col_name.lower()

    # Dates / Months
    if "month" in name:
        months = ["september", "october", "november", "december"]
        return months[row_idx % len(months)]
    if "date" in name:
        # simple YYYY-MM-DD
        base_days = [1, 8, 15, 22]
        day = base_days[row_idx % len(base_days)]
        return f"2024-10-{day:02d}"

    # Names
    if "student" in name:
        students = ["Jack Garcia", "Tatiana Ortiz", "Carter Sanchez", "Maria Lopez"]
        return students[row_idx % len(students)]
    if "vendor" in name or "provider" in name:
        vendors = ["Always Home Nursing", "Healthcare Solutions LLC", "Sunrise Pediatrics"]
        return vendors[row_idx % len(vendors)]
    if "clinician" in name or "nurse" in name:
        clinicians = ["Nurse Williams", "Therapist Kim", "Clinician Patel"]
        return clinicians[row_idx % len(clinicians)]
    if "district" in name:
        districts = ["Northside Unified", "Lakeview ISD", "Hillside USD"]
        return districts[row_idx % len(districts)]

    # Metrics / numbers
    if any(k in name for k in ["hours", "qty", "quantity"]):
        return round(5 + row_idx * 2.5, 2)
    if any(k in name for k in ["cost", "spend", "amount", "total", "rate"]):
        return round(1500 + row_idx * 750.25, 2)
    if "count" in name:
        return 3 + row_idx

    # Status / generic
    if "status" in name:
        statuses = ["paid", "pending", "void"]
        return statuses[row_idx % len(statuses)]

    # Fallback string
    return f"value_{row_idx + 1}"


def build_html_table(rows: list[dict]) -> str:
    """
    Simple HTML <table> builder from rows.
    """
    if not rows:
        return "<p>No data available for this synthetic example.</p>"

    columns = list(rows[0].keys())
    html = ["<table>", "<thead><tr>"]
    html.extend(f"<th>{col}</th>" for col in columns)
    html.append("</tr></thead><tbody>")
    for r in rows:
        html.append("<tr>")
        for col in columns:
            html.append(f"<td>{r.get(col, '')}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def synthesize_text(canonical_sql: str, user_text: str) -> str:
    """
    Create a short narrative based on canonical_sql and/or user_text.
    """
    sql_lower = canonical_sql.lower() if canonical_sql else ""
    if "hours" in sql_lower:
        return "Here are the service hours for your request, summarized by the relevant dimensions."
    if "total_cost" in sql_lower or "spend" in sql_lower or "cost" in sql_lower:
        return "Here is the cost summary for your request, summarized by the relevant dimensions."
    if "invoice" in sql_lower:
        return "Here are the invoices matching your request."
    return "Here is the report for your request."


def synthesize_assistant_payload(
    canonical_id: str,
    canonical_sql: str,
    user_text: str,
    cot_reasoning: str | None = None,
    num_rows: int = 3,
) -> dict:
    """
    Core of Option 2: auto-populate NLV assistant outputs.

    For each canonical:
      - infer output columns from SELECT,
      - generate synthetic rows,
      - build HTML table,
      - write a short narrative.

    This converts NLV "shell" records into real supervision.
    """
    cols = extract_select_columns(canonical_sql)
    if not cols:
        # Fallback generic schema if we can't parse SQL
        cols = ["label", "value"]

    rows = []
    for i in range(num_rows):
        row = {}
        for col in cols:
            row[col] = fake_value_for_column(col, i)
        rows.append(row)

    html = build_html_table(rows)
    text = synthesize_text(canonical_sql, user_text)

    return {
        "text": text,
        "rows": rows,
        "html": html,
    }


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
    Parse edge_cases.md of the form:

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

        user_text = decode_maybe_json_string(raw_user)
        asst_text = decode_maybe_json_string(raw_asst)
        cot_text  = decode_maybe_json_string(raw_cot) if raw_cot else ""

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
    Parse multi_turn_data.md of the form:

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

        for ln in lines:
            # TurnN_User: ...
            m_user = re.match(r"Turn(\d+)_User:\s*(.+)", ln)
            if m_user:
                turn = m_user.group(1)
                raw = m_user.group(2).strip()
                text = decode_maybe_json_string(raw)
                messages.append({"role": "user", "content": text})
                continue

            # TurnN_Assistant_Text: ...
            m_ast_text = re.match(r"Turn(\d+)_Assistant_Text:\s*(.+)", ln)
            if m_ast_text:
                turn = m_ast_text.group(1)
                raw = m_ast_text.group(2).strip()
                decoded = decode_maybe_json_string(raw)
                messages.append({"role": "assistant", "content": decoded})
                continue

            # TurnN_Assistant_Output_JSON: "{\"sql\": \"...\"}"
            m_ast_json = re.match(r"Turn(\d+)_Assistant_Output_JSON:\s*(.+)", ln)
            if m_ast_json:
                turn = m_ast_json.group(1)
                raw = m_ast_json.group(2).strip()
                decoded = decode_maybe_json_string(raw)
                messages.append({"role": "assistant", "content": decoded})
                continue

            # TurnN_CoT: ...
            m_cot = re.match(r"Turn(\d+)_CoT:\s*(.+)", ln)
            if m_cot:
                turn = m_cot.group(1)
                raw_cot = m_cot.group(2).strip()
                cot_by_turn[turn] = decode_maybe_json_string(raw_cot)
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
        # 1) NLV → Canonical (auto-populated assistant payloads)
        # --------------------------------------------------
        for entry in nlv_entries:
            cid = entry["canonical_id"]
            nlv_text = entry["nlv_text"]

            if cid not in canonical_sql_map:
                print(f"  ⚠ Canonical ID {cid} (NLV {entry['nlv_id']}) not in canonical.md, skipping.")
                continue

            canonical_sql = canonical_sql_map.get(cid, "")
            cot_text = cot_map.get(cid)

            asst_payload = synthesize_assistant_payload(
                canonical_id=cid,
                canonical_sql=canonical_sql,
                user_text=nlv_text,
                cot_reasoning=cot_text,
            )

            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": nlv_text},
                    {
                        "role": "assistant",
                        "content": json.dumps(asst_payload, ensure_ascii=False),
                    },
                ],
                "canonical_id": cid,
                "canonical_sql": canonical_sql,
            }

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
            # keep CoT as metadata if present
            if "cot_reasoning" in ec and ec["cot_reasoning"]:
                record["cot_reasoning"] = ec["cot_reasoning"]
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            edge_count += 1

        # --------------------------------------------------
        # 3) Multi-turn dialogs
        # --------------------------------------------------
        for mt in multi_turn_convos:
            messages = [{"role": "system", "content": system_prompt}] + mt["messages"]
            record = {"messages": messages}
            if "cot_reasoning" in mt and mt["cot_reasoning"]:
                record["cot_reasoning"] = mt["cot_reasoning"]
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
