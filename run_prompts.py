from openai import OpenAI
import requests
import os
from datetime import datetime

# Use environment variables for GitHub Actions
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
    if response.status_code != 200:
        print("❌ Failed to fetch prompts:", response.text)
        return []
    return response.json()


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
    lines = result_text.lower().split("\n")
    print(f"🔎 Checking brand '{brand_name}' in result...")
    for idx, line in enumerate(lines):
        print(f"   Line {idx+1}: {line.strip()}")
        if brand_name in line:
            print(f"✅ Brand matched on line {idx+1}")
            return str(idx + 1)
    print("❌ Brand not found in result.")
    return None


def upload_result(prompt_id, brand_id, prompt_text, result, position=None):
    if position == "11":
        print("⚠️ Position is 11, forcing to None to comply with DB constraint.")
        position = None

    payload = {
        "prompt_id": prompt_id,
        "brand_id": brand_id,
        "prompt_text": prompt_text,
        "result": result,
        "created_at": datetime.utcnow().isoformat(),
    }
    if position is not None:
        payload["position"] = position

    print(f"\n📤 Uploading to Supabase:")
    print(f"   Prompt ID: {prompt_id}")
    print(f"   Brand ID: {brand_id}")
    print(f"   Position: {position}")
    print(f"   Prompt: {prompt_text}")
    print(f"   Result Preview: {result[:200].strip()}...\n")

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/prompt_results",
        headers={**headers, "Content-Type": "application/json"},
        json=payload
    )
    if response.status_code not in [200, 201]:
        print("❌ Upload failed:", response.text)
    else:
        print(f"✅ Uploaded result for: '{prompt_text}'")


def main():
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    prompts = fetch_prompts()
    print(f"📦 Found {len(prompts)} prompts")

    for prompt in prompts:
        prompt_text = prompt["prompt_text"]
        brand_id = prompt["brand_id"]
        prompt_id = prompt["id"]
        brand_name = prompt.get("brand", {}).get("name", "").strip().lower()

        print(f"\n🧠 Evaluating prompt: '{prompt_text}' for brand: {brand_name.title()}")
        result = run_prompt(prompt_text)
        position = None

        if isinstance(result, str) and brand_name:
            position = get_position_from_result(result, brand_name)

        print(f"📢 FINAL POSITION USED: {position}")
        upload_result(prompt_id, brand_id, prompt_text, result, position)

    print("✅ Done.")


if __name__ == "__main__":
    main()
