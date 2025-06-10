import openai
import requests
import os
from datetime import datetime
import time

# Load secrets from GitHub Actions
openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

# Step 1: Get all prompts with brand info
def fetch_prompts():
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/prompts?select=*,brand:brands(name)",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
        }
    )
    if res.status_code != 200:
        raise Exception(f"❌ Failed to fetch prompts: {res.status_code} → {res.text}")
    return res.json()


# Step 2: Evaluate a prompt
def evaluate_prompt(prompt_id, prompt_text, brand_id, brand_name):
    print(f"🧠 Evaluating: {prompt_text}")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}]
        )
        result_text = response['choices'][0]['message']['content']
        mentioned = brand_name.lower() in result_text.lower()
        position = 1 if mentioned else 11

        payload = {
            "prompt_id": prompt_id,
            "brand_id": brand_id,
            "ai_result": result_text,
            "position": position,
            "brand_mentioned": mentioned,
        }

        # Step 3: Save result to Supabase
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/prompt_results",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        )

        if res.status_code == 201:
            print(f"✅ Uploaded result for: {prompt_text}")
        else:
            print(f"❌ Upload failed: {res.status_code} → {res.text}")
        time.sleep(1)  # Optional throttle

    except Exception as e:
        print(f"⚠️ Error for prompt '{prompt_text}': {e}")


# Step 4: Run the full loop
def run_all():
    print(f"🚀 Running daily prompt evaluation @ {datetime.utcnow().isoformat()}")
    prompts = fetch_prompts()
    for p in prompts:
        evaluate_prompt(p["id"], p["prompt_text"], p["brand_id"], p["brand"]["name"])
    print("✅ All done.")

if __name__ == "__main__":
    run_all()
