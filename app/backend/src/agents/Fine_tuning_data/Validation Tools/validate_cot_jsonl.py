import json
import hashlib
from pathlib import Path

# ============================================================
# 🔧 PLUG YOUR JSONL FILE PATH HERE ↓
# ============================================================

JSONL_PATH = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\cot_finetuning_data.jsonl"
)

# ============================================================
# VALIDATOR LOGIC (NO CHANGES NEEDED BELOW THIS LINE)
# ============================================================

def is_probably_json(s: str) -> bool:
    s = s.strip()
    return s.startswith("{") and s.endswith("}")


def normalize_record_for_hash(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def validate_assistant_json(asst_raw, strict, lineno, errors, rec_kind):
    """
    Validate assistant content when it looks like JSON.

    SQL-only multi-turn messages look like:
        {"sql": "..."}
    These should be accepted.
    """
    try:
        asst = json.loads(asst_raw)
    except Exception as e:
        errors.append(f"[line {lineno}] invalid assistant JSON: {e}")
        return

    # =====================================================
    # NEW: Allow SQL-only assistant messages (multi-turn)
    # =====================================================
    if isinstance(asst, dict) and set(asst.keys()) == {"sql"}:
        return  # VALID multi-turn assistant, no need for text/rows/html

    # Normal JSON validation (NLV or positive examples)
    text = asst.get("text")
    rows = asst.get("rows")
    html = asst.get("html")

    if not isinstance(text, str):
        errors.append(f"[line {lineno}] missing 'text' in assistant ({rec_kind})")

    if rows is not None and not isinstance(rows, list):
        errors.append(f"[line {lineno}] 'rows' must be list or null ({rec_kind})")

    if not isinstance(html, str):
        errors.append(f"[line {lineno}] missing 'html' field ({rec_kind})")

    if strict:
        if not text.strip():
            errors.append(f"[line {lineno}] empty 'text' in strict mode ({rec_kind})")
        if rows is None or len(rows) == 0:
            errors.append(f"[line {lineno}] empty or null 'rows' in strict mode ({rec_kind})")
        if not html.strip():
            errors.append(f"[line {lineno}] empty 'html' in strict mode ({rec_kind})")


def validate_file(path: Path):
    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    total_records = 0
    nlv_records = 0
    other_records = 0

    errors = []
    seen_hashes = {}
    duplicates = []

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            total_records += 1

            try:
                obj = json.loads(line)
            except Exception as e:
                errors.append(f"[line {lineno}] invalid JSONL: {e}")
                continue

            # Duplicate detection
            rec_hash = hashlib.sha256(normalize_record_for_hash(obj).encode()).hexdigest()
            if rec_hash in seen_hashes:
                duplicates.append((lineno, seen_hashes[rec_hash]))
            else:
                seen_hashes[rec_hash] = lineno

            # Determine category
            is_nlv = "canonical_id" in obj
            if is_nlv:
                nlv_records += 1
                rec_kind = "nlv"
            else:
                other_records += 1
                rec_kind = "other"

            messages = obj.get("messages", [])
            if not isinstance(messages, list) or len(messages) == 0:
                errors.append(f"[line {lineno}] missing messages[]")
                continue

            # Validate assistant messages
            for msg in messages:
                if msg.get("role") != "assistant":
                    continue

                content = msg.get("content", "")
                if is_probably_json(content):
                    validate_assistant_json(
                        content,
                        strict=is_nlv,  # strict only for NLV with canonical_id
                        lineno=lineno,
                        errors=errors,
                        rec_kind=rec_kind,
                    )
                else:
                    # Non-JSON assistants are fine for non-NLV entries
                    if is_nlv:
                        errors.append(f"[line {lineno}] canonical record has non-JSON assistant")

    # RESULTS
    print("===============================================")
    print(f"Validated file: {path}")
    print("===============================================")
    print(f"Total records:       {total_records}")
    print(f"NLV records:         {nlv_records}")
    print(f"Other records:       {other_records}")
    print(f"Unique records:      {len(seen_hashes)}")

    if duplicates:
        print("\n⚠ Duplicate records detected:")
        for ln, first in duplicates[:10]:
            print(f"  Line {ln} duplicates line {first}")
        if len(duplicates) > 10:
            print(f"  … plus {len(duplicates)-10} more.")

    if errors:
        print("\n❌ ERRORS FOUND:")
        for e in errors[:25]:
            print(" ", e)
        if len(errors) > 25:
            print(f"  … plus {len(errors)-25} more.")
    else:
        print("\n✅ Validation passed with no errors.")


# Run immediately
validate_file(JSONL_PATH)
