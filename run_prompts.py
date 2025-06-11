from openai import OpenAI
import requests
import os
from datetime import datetime

# ✅ Environment vars (set these in GitHub Secrets or your .env)
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
}

# ✅ Fetch prompts from Supabase
def fetch_prompts():
    print("📦 Fetching prompts from Supabase...")
    url = f"{SUPABASE_URL}/rest/v1/prompts?select=*,brand:brands!prompts_brand_id_fkey(name)"
    response = requests.get(url, headers=headers)
    print(f"🔍 Fetch status: {response.status_code}")
    if response.status_code != 200:
        print("❌ Failed to fetch prompts:", response.text)
        return []
    return response.json()

# ✅ Call OpenAI to evaluate the prompt
def run_prompt(prompt_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# ✅ Extract brand position
def get_position_from_result(result_text, brand_name):
    print(f"🔎 Checking brand '{brand_name}' in result...")
    lines = result_text.lower().split("\n")
    for idx, line in enumerate(lines):
        print(f"   Line {idx+1}: {line.strip()}")
        if brand_name in line:
            print(f"✅ Brand found at line {idx+1}")
            return str(idx + 1)
    print("❌ Brand not found in result.")
    return None

# ✅ Upload result to Supabase
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

    print(f"\n📤 Uploading to Supabase:")
    print(f"   Prompt ID: {prompt_id}")
    print(f"   Brand ID: {brand_id}")
    print(f"   Position: {position}")
    print(f"   Prompt: {prompt_text}")
    print(f"   Result Preview: {result[:300]}...\n")

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/prompt_results",
        headers={**headers, "Content-Type": "application/json"},
        json=payload
    )
    if response.status_code not in [200, 201]:
        print("❌ Upload failed:", response.text)
    else:
        print("✅ Uploaded result")

# ✅ Main runner
def main():
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    prompts = fetch_prompts()
    print(f"📦 Found {len(prompts)} prompts")

    for idx, prompt in enumerate(prompts):
        prompt_text = prompt["prompt_text"]
        brand_id = prompt["brand_id"]
        prompt_id = prompt["id"]
        brand_name = prompt.get("brand", {}).get("name", "").strip().lower()

        print(f"\n=== Prompt {idx + 1} ===")
        print(f"🧐 Prompt: {prompt_text}")
        print(f"🔍 Brand: {brand_name}")

        result = run_prompt(prompt_text)
        position = None

        if isinstance(result, str) and brand_name:
            position = get_position_from_result(result, brand_name)

        print(f"📢 FINAL POSITION USED: {position}")
        upload_result(prompt_id, brand_id, prompt_text, result, position)

    print("✅ Done.")

if __name__ == "__main__":
    main()
