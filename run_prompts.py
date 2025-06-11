from openai import OpenAI
import requests
import os
import sys
from datetime import datetime

# ✅ Set your environment variables (GitHub Actions will inject them)
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
}

# ✅ Fetch prompts
def fetch_prompts():
    print("📦 Fetching prompts from Supabase...")
    url = f"{SUPABASE_URL}/rest/v1/prompts?select=*,brand:brands!prompts_brand_id_fkey(name)"
    response = requests.get(url, headers=headers)
    print(f"🔍 Fetch status: {response.status_code}")
    if response.status_code != 200:
        print("❌ Failed to fetch prompts:", response.text)
        return []
    return response.json()

# ✅ Run GPT prompt
def run_prompt(prompt_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# ✅ Get brand position
def get_position_from_result(result_text, brand_name):
    brand_name = brand_name.lower().strip()
    lines = result_text.lower().split("\n")
    for idx, line in enumerate(lines):
        print(f"   🔍 Line {idx+1}: {line.strip()}")
        if brand_name in line:
            print(f"✅ Brand found at position {idx+1}", flush=True)
            return str(idx + 1)
    print("❌ Brand not found", flush=True)
    return None

# ✅ Upload result
def upload_result(prompt_id, brand_id, prompt_text, result, position=None):
    payload = {
        "prompt_id": prompt_id,
        "brand_id": brand_id,
        "prompt_text": prompt_text,
        "result": result,
        "created_at": datetime.utcnow().isoformat()
    }
    if position is not None:
        payload["position"] = position

    print(f"📤 Uploading result:", flush=True)
    print(f"   Prompt: {prompt_text}", flush=True)
    print(f"   Position: {position}", flush=True)

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/prompt_results",
        headers={**headers, "Content-Type": "application/json"},
        json=payload
    )
    if response.status_code not in [200, 201]:
        print("❌ Upload failed:", response.text, flush=True)
    else:
        print("✅ Uploaded result", flush=True)

# ✅ Main runner
def main():
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC", flush=True)
    prompts = fetch_prompts()
    print(f"📦 Found {len(prompts)} prompts", flush=True)

    for idx, prompt in enumerate(prompts):
        prompt_text = prompt["prompt_text"]
        brand_id = prompt["brand_id"]
        prompt_id = prompt["id"]
        brand_name = prompt.get("brand", {}).get("name", "").strip()

        print(f"\n🧠 Evaluating Prompt {idx + 1}: '{prompt_text}' for brand: {brand_name}", flush=True)

        result = run_prompt(prompt_text)
        position = None

        if isinstance(result, str) and brand_name:
            position = get_position_from_result(result, brand_name)

        print(f"📢 Final Position: {position}", flush=True)
        upload_result(prompt_id, brand_id, prompt_text, result, position)

    print("✅ Done.", flush=True)

if __name__ == "__main__":
    main()
