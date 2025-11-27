import json
from pathlib import Path

# -----------------------------------
# CONFIGURATION
# -----------------------------------
GOOD_INPUT_FILE = "Fine_tuning_data/Canonical Data/canonical_query_testing_results.jsonl"  # from your classifier
SYSTEM_PROMPT_FILE = "system_prompt.txt"       # full system prompt
OUTPUT_FILE = "Fine_tuning_data/Canonical Data/canonical_finetuning_data.jsonl"  # output fine-tune dataset


def load_system_prompt():
    """Load the raw system prompt text exactly as-is."""
    path = Path(SYSTEM_PROMPT_FILE)
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {SYSTEM_PROMPT_FILE}")
    return path.read_text(encoding="utf-8")


def convert_record(rec, system_prompt):
    """
    Convert a single evaluation record into OpenAI fine-tuning format.

    Expected record structure:
    {
        "id": ...,
        "question": "...",
        "text": "...",
        "sql_used": "...",   # optional
        "rows": [...],
        "html": "..."
    }
    """
    # Build assistant JSON response (must be single string)
    assistant_payload = {
        "text": rec.get("text", "") or "",
        "rows": rec.get("rows", None),
        "html": rec.get("html", "") or "",
    }

    assistant_json = json.dumps(assistant_payload, ensure_ascii=False)

    # Build messages list for fine-tuning
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": rec["question"]},
        {"role": "assistant", "content": assistant_json}
    ]

    return {"messages": messages}


def convert_file():
    system_prompt = load_system_prompt()

    input_path = Path(GOOD_INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {GOOD_INPUT_FILE}")

    with input_path.open("r", encoding="utf-8") as fin, \
         output_path.open("w", encoding="utf-8") as fout:

        for line in fin:
            if not line.strip():
                continue

            rec = json.loads(line)
            converted = convert_record(rec, system_prompt)
            fout.write(json.dumps(converted, ensure_ascii=False) + "\n")

    print(f"\n✔ Fine-tuning dataset created!")
    print(f"➡ {OUTPUT_FILE}")


if __name__ == "__main__":
    convert_file()
