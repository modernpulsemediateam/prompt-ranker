import os
import requests
from openai import OpenAI
from datetime import datetime

# Load secrets from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# OpenAI client for new SDK (v1+)
client = OpenAI(api_key=OPENAI_API_KEY)

# STEP 1: Fetch prompts from Supabase
def fetch_prompts():
    print("📦 Fetching prompts from Supabase...")
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/prompts?select=*,brand:brands(name)",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )
    print(f"🔍 Fetch status: {res.status_code}")
    if res.status_code != 200:
        print(f"❌ Failed to fetch prompts: {res.text}")
        return []
    prompts = res.json()
    print(f"📦 Found {len(prompts)} prompts")
    return prompts

# STEP 2: Evaluate prompt with OpenAI and upload results
def evaluate_prompt(prompt_id, prompt_text, brand_id, brand_name):
    print(f"\n🧠 Evaluating prompt: '{prompt_text}' for brand: {brand_name}")
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo" if preferred
            messages=[{"role": "user", "content": prompt_text}]
        )
        result_text = response.choices[0].message.content
        mentioned = brand_name.lower() in result_text.lower()
        position = 1 if mentioned else 11

        payload = {
            "prompt_id": prompt_id,
            "brand_id": brand_id,
            "ai_result": result_text,
            "position": position,
            "brand_mentioned": mentioned
        }

        print("📤 Uploading result to Supabase...")
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/prompt_results",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        )

        if res.status_code == 201:
            print(f"✅ Uploaded result for: '{prompt_text}'")
        else:
            print(f"❌ Upload failed: {res.status_code} → {res.text}")

    except Exception as e:
        print(f"⚠️ OpenAI Error for prompt '{prompt_text}': {e}")

# STEP 3: Run all prompts
def run_all():
    print(f"\n🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    prompts = fetch_prompts()
    for p in prompts:
        evaluate_prompt(p["id"], p["prompt_text"], p["brand_id"], p["brand"]["name"])
    print("\n✅ Done.")

if __name__ == "__main__":
    run_all()
