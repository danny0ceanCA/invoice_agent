import json
import time
import requests
import os
from datetime import date

# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "https://care-spend-com.onrender.com/api/agents/analytics"

# IMPORTANT: Must be a VALID Auth0 ACCESS TOKEN with audience "https://invoice-api/"
ACCESS_TOKEN = "PASTE_YOUR_ACCESS_TOKEN_HERE"

DISTRICT_KEY = "I51P-DA8D-HJQ0"


# ============================================================
# PATH HANDLING — THIS IS THE FIX
# ============================================================

# Directory where THIS script actually lives, i.e., /agents/testing/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# JSON file in the same directory
INPUT_FILE = os.path.join(SCRIPT_DIR, "questions.json")

# Output file also in same directory
OUTPUT_FILE = os.path.join(SCRIPT_DIR, f"render_eval_output_{date.today()}.jsonl")


# ============================================================
# HIT RENDER ANALYTICS AGENT
# ============================================================

def call_render_agent(question, session_id):
    payload = {
        "query": question,
        "context": {
            "district_key": DISTRICT_KEY,
            "session_id": session_id
        }
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(API_URL, json=payload, headers=headers)
    status = response.status_code
    raw_text = response.text

    try:
        json_data = response.json()
    except Exception:
        json_data = None

    return status, raw_text, json_data


# ============================================================
# MAIN RUNNER
# ============================================================

def run_eval():
    print("\n🔍 Running Render analytics tests…")
    print("--------------------------------------------------")
    print(f"Questions file: {INPUT_FILE}")
    print(f"Output file:    {OUTPUT_FILE}\n")

    # Load questions safely
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: questions.json not found:\n{INPUT_FILE}")
        return

    try:
        with open(INPUT_FILE, "r") as f:
            questions = json.load(f)
    except Exception as e:
        print(f"❌ ERROR reading JSON: {e}")
        return

    with open(OUTPUT_FILE, "w") as out:
        for row in questions:
            qid = row.get("id")
            question = row["question"]

            session_id = f"render-test-{qid}-{int(time.time())}"

            print(f"▶ Q{qid}: {question}")

            status, raw_text, json_data = call_render_agent(question, session_id)

            if json_data is None:
                print(f"   ❌ JSON decode failed (status={status})")
                print(f"   RAW FULL RESPONSE:\n{raw_text}\n")

                out.write(json.dumps({
                    "id": qid,
                    "question": question,
                    "status": status,
                    "raw_text": raw_text,
                    "error": "JSON decode failed"
                }) + "\n")

            else:
                print(f"   ✔ OK (status={status})")
                out.write(json.dumps({
                    "id": qid,
                    "question": question,
                    "status": status,
                    "response": json_data
                }) + "\n")

            time.sleep(0.5)

    print("\n🎉 DONE — results saved to:", OUTPUT_FILE)
    print("Check Render logs for backend activity.\n")


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    run_eval()
