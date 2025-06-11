from openai import OpenAI
import requests
import os
from datetime import datetime

# Environment setup
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
}

def fetch_prompts():
    print("📦 Fetching prompts from Supabase...")
    url = f"{SUPABASE_URL}/rest/v1/prompts?select=*,brand:brands!prompts_brand_id_fkey(name)"
    response = requests.get(url, headers=headers)
    print(f"🔍 Fetch status: {response.status_code}")
    return response.json() if response.status_code == 200 else []

def run_prompt(prompt_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def get_position_from_result(result_text, brand_name):
    brand_name = brand_name.lower().strip()
    lines = result_text.lower().split("\n")

    for idx, line in enumerate(lines):
        print(f"   Line {idx + 1}: {line.strip()}")
        if brand_name in line:
            print(f"✅ Brand found at line {idx + 1}")
            return idx + 1
    print("❌ Brand not found.")
    return None

def upload_result(prompt_id, brand_id, prompt_text, result, position, brand_name):
    print(f"\n📤 Uploading result for prompt: {prompt_text}")
    print(f"📢 Calculated position: {position}")

    # If position is None or 11, skip uploading
    if position is None:
        print("⛔ Skipping upload — no position found.")
        return
    if str(position).strip() == "11":
        print("⛔ Skipping upload — illegal position 11.")
        return

    payload = {
        "prompt_id": prompt_id,
        "brand_id": brand_id,
        "prompt_text": prompt_text,
        "brand_name": brand_name,
        "result": result,
        "position": position,
        "created_at": datetime.utcnow().isoformat()
    }

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/prompt_results",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
    )

    if response.status_code not in [200, 201]:
        print("❌ Upload failed:", response.text)
    else:
        print("✅ Uploaded successfully")

def main():
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    prompts = fetch_prompts()
    print(f"📦 Found {len(prompts)} prompts")

    for prompt in prompts:
        prompt_text = prompt["prompt_text"]
        brand_id = prompt["brand_id"]
        prompt_id = prompt["id"]
        brand_name = prompt.get("brand", {}).get("name", "").strip()

        print(f"\n🧠 Evaluating prompt: '{prompt_text}' for brand: {brand_name}")
        result = run_prompt(prompt_text)

        if not result:
            print("❌ No result returned.")
            continue

        position = get_position_from_result(result, brand_name)
        upload_result(prompt_id, brand_id, prompt_text, result, position, brand_name)

    print("✅ Done.")

if __name__ == "__main__":
    main()
