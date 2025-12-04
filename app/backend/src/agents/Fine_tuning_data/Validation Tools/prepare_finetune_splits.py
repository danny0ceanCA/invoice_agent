import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ============================================================
# 🔧 EDIT THESE THREE PATHS ↓↓↓
# ============================================================

INPUT_JSONL = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\cot_finetuning_data.jsonl"
)

TRAIN_OUT = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\cot_finetuning_train.jsonl"
)

VAL_OUT = Path(
    r"C:\Users\danie\Documents\invoice_agent\app\backend\src\agents\Fine_tuning_data\CoT\cot_finetuning_val.jsonl"
)

VAL_RATIO = 0.10   # 10% validation split
SEED = 42
# ============================================================


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def normalize_record(rec: Dict[str, Any]) -> str:
    return json.dumps(rec, sort_keys=True, ensure_ascii=False)


def is_probably_json(s: str) -> bool:
    s = s.strip()
    return s.startswith("{") and s.endswith("}")


def classify(rec: Dict[str, Any]) -> str:
    if "canonical_id" in rec:
        return "nlv"

    msgs = rec.get("messages", [])
    if not isinstance(msgs, list):
        return "other"

    if len(msgs) > 3:
        return "multi"

    if len(msgs) == 3:
        assistant = msgs[2]
        content = assistant.get("content", "")
        if isinstance(content, str) and is_probably_json(content):
            return "positive"
        else:
            return "edge"

    return "other"


def stratified_split(records: List[Dict[str, Any]], val_ratio: float):
    random.seed(SEED)

    # Deduplicate
    seen = set()
    unique = []
    for rec in records:
        h = normalize_record(rec)
        if h not in seen:
            seen.add(h)
            unique.append(rec)

    # Group by type
    groups = {"nlv": [], "multi": [], "positive": [], "edge": [], "other": []}
    for rec in unique:
        kind = classify(rec)
        groups.setdefault(kind, []).append(rec)

    train, val = [], []

    # Split each group
    for kind, recs in groups.items():
        if not recs:
            continue
        random.shuffle(recs)

        if len(recs) == 1:
            val_count = 0
        else:
            val_count = max(1, int(round(len(recs) * val_ratio)))

        val.extend(recs[:val_count])
        train.extend(recs[val_count:])

    random.shuffle(train)
    random.shuffle(val)

    return train, val


def write_jsonl(path: Path, records: List[Dict[str, Any]]):
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    print("Loading input file…")
    records = load_jsonl(INPUT_JSONL)
    print(f"Total raw records: {len(records)}")

    train, val = stratified_split(records, VAL_RATIO)

    print(f"Writing train split → {TRAIN_OUT}")
    write_jsonl(TRAIN_OUT, train)

    print(f"Writing val split   → {VAL_OUT}")
    write_jsonl(VAL_OUT, val)

    print("===========================================")
    print(f"Train count: {len(train)}")
    print(f"Val count:   {len(val)}")
    print("Done.")
    print("===========================================")


if __name__ == "__main__":
    main()
