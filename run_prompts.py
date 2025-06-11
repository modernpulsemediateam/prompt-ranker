import os
import openai
import requests
from datetime import datetime

# Load environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

openai.api_key = OPENAI_API_KEY

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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}],
        )
        return response.choices[0].message["content"]
    except Exception as e:
        print(f"⚠️ Error with '{prompt_text}':", str(e))
        return None

def upload_result(prompt_id, brand_id, prompt_text, result, position):
    payload = {
        "prompt_id": prompt_id,
        "brand_id": brand_id,
        "prompt_text": prompt_text,
        "result": result,
        "position": str(position),
        "created_at": datetime.utcnow().isoformat()
    }
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/prompt_results",
        headers={**headers, "Content-Type": "application/json"},
        json=payload
    )
    if response.status_code not in [200, 201]:
        print("❌ Upload failed:", response.text)
    else:
        print("✅ Uploaded result")

def main():
    prompts = fetch_prompts()
    print(f"📦 Found {len(prompts)} prompts")

    for prompt in prompts:
        prompt_text = prompt["prompt_text"]
        brand_id = prompt["brand_id"]
        prompt_id = prompt["id"]
        brand_name = prompt.get("brand", {}).get("name", "").strip().lower()

        print(f"🧐 Evaluating prompt: {prompt_text} for brand: {brand_name}")

        result = run_prompt(prompt_text)

        if result:
            result_lower = result.lower()

            if brand_name and brand_name in result_lower:
                position = "1"
            else:
                position = "Not Ranking"

            upload_result(prompt_id, brand_id, prompt_text, result, position)
        else:
            print(f"⚠️ No result returned for prompt: {prompt_text}")

    print("✅ Done.")

if __name__ == "__main__":
    print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    main()
