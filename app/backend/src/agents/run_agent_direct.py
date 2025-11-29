import json
import datetime
from app.backend.src.agents.district_analytics_agent import run_analytics_agent

INPUT_FILE = "01_district_eval_questions.jsonl"
OUTPUT_FILE = f"agent_direct_eval_output_{datetime.date.today()}.jsonl"

# This must match your real district_key
BASE_USER_CONTEXT = {
    "district_key": "I51P-DA8D-HJQ0",
    "district_id": 1,              # optional
}

def run_direct_eval():
    with open(INPUT_FILE, "r") as f, open(OUTPUT_FILE, "w") as out:
        for line in f:
            row = json.loads(line)
            qid = row["id"]
            question = row["question"]

            print(f"Running Q{qid}: {question}")

            try:
                # DIRECT AGENT CALL (no http, no auth0)
                user_context = dict(BASE_USER_CONTEXT)
                user_context["user_id"] = f"eval-{qid}"
                result = run_analytics_agent(question, user_context)

                out.write(json.dumps({
                    "id": qid,
                    "question": question,
                    "text": result.text,
                    "sql_used": getattr(result, "debug_sql", None),
                    "rows": result.rows,
                    "html": result.html
                }) + "\n")

                print(f"✔ Completed Q{qid}")

            except Exception as exc:
                out.write(json.dumps({
                    "id": qid,
                    "question": question,
                    "error": str(exc)
                }) + "\n")

                print(f"✖ Error on Q{qid}: {exc}")

    print("\nDONE. Output saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    run_direct_eval()
