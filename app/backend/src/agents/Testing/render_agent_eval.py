import json
import time
import os
from datetime import date

from app.backend.src.agents.district_analytics_agent import run_analytics_agent

DISTRICT_KEY = "I51P-DA8D-HJQ0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "questions.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, f"render_direct_eval_{date.today()}.jsonl")

def run_eval():
    print("\n🔍 Running INTERNAL Render analytics eval (no HTTP, no Auth0)…")
    print("---------------------------------------------------------------")
    print(f"Questions file: {INPUT_FILE}")
    print(f"Output file:    {OUTPUT_FILE}\n")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: questions.json not found:\n{INPUT_FILE}")
        return

    with open(INPUT_FILE, "r") as f:
        questions = json.load(f)

    with open(OUTPUT_FILE, "w") as out:
        for row in questions:
            qid = row.get("id")
            question = row["question"]

            print(f"▶ Q{qid}: {question}")

            session_id = f"internal-eval-{qid}-{int(time.time())}"

            # DIRECT INTERNAL CALL — bypasses Auth0 & HTTP
            result = run_analytics_agent(
                question,
                {
                    "district_key": DISTRICT_KEY,
                    "session_id": session_id
                },
            )

            out.write(json.dumps({
                "id": qid,
                "question": question,
                "text": result.text,
                "html": result.html,
                "rows": result.rows,
                "sql_used": getattr(result, "debug_sql", None),
            }) + "\n")

            print(f"   ✔ DONE\n")
            time.sleep(0.3)

    print("\n🎉 FINISHED — Internal eval results saved to:")
    print(OUTPUT_FILE)

if __name__ == "__main__":
    run_eval()
