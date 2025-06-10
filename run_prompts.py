import openai
import requests
import os
from datetime import datetime
import time

openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

PROMPTS = [
    {"brand": "Spectrum", "prompt": "internet in midland, tx"},
    {"brand": "Spectrum", "prompt": "internet in crystal beach, tx"},
    {"brand": "AT&T", "prompt": "fiber internet in dallas"},
]

def evaluate_prompt(prompt_text, brand_name):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}]
        )
        result_text = response['choices'][0]['message']['content']
        mentioned = brand_name.lower() in result_text.lower()
        position = 1 if mentioned else 11

        payload = {
            "brand_name": brand_name,
            "prompt_text": prompt_text,
            "brand_mentioned": mentioned,
            "ai_result": result_text,
            "position": position
        }

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
            print(f"✅ Uploaded: {prompt_text}")
        else:
            print(f"❌ Failed for {prompt_text}: {res.status_code} → {res.text}")
        time.sleep(1)

    except Exception as e:
        print(f"⚠️ Error with '{prompt_text}': {e}")

def run_all_prompts():
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    for item in PROMPTS:
        evaluate_prompt(item["prompt"], item["brand"])
    print("✅ All done!")

if __name__ == "__main__":
    run_all_prompts()
