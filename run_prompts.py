import os
import openai
import requests
import uuid
from datetime import datetime
from supabase import create_client, Client
import re

# Set up OpenAI and Supabase
openai.api_key = os.environ['OPENAI_API_KEY']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Logging helper
def log(msg):
    print(msg, flush=True)

# Extract position from AI response (1–10 only, else None)
def extract_position(response_text, target_brand):
    lines = response_text.strip().splitlines()
    for line in lines:
        match = re.match(r"(\d+)\.\s", line.strip())
        if match:
            num = int(match.group(1))
            if 1 <= num <= 10:
                # Check if this line mentions the target brand
                if target_brand.lower() in line.lower():
                    return num
    return None  # Brand not found in positions 1-10

# Evaluate a single prompt
def evaluate_prompt(prompt, brand):
    full_prompt = f"You are ranking search relevance. A user searched for: '{prompt}'\nBrand: {brand}\n\nGive a list of search results ranked by relevance."
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.5,
            max_tokens=500
        )
        result_text = response.choices[0].message.content.strip()
        position = extract_position(result_text, brand)
        return result_text, position
    except Exception as e:
        log(f"❌ Error evaluating prompt '{prompt}': {e}")
        return None, None

# Upload results to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    log(f"📤 Uploading result to Supabase...")
    try:
        data = {
            "id": str(uuid.uuid4()),
            "prompt_id": prompt_id,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "response": result_text,
            "position": position,
            "success": position is not None,
            "date": datetime.utcnow().date().isoformat(),
            "brand": brand,
            "prompt_text": original_prompt,
            "created_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("prompt_results").insert(data).execute()
        if res.status_code == 201:
            log(f"✅ Uploaded result for: '{original_prompt}'")
        else:
            log(f"❌ Upload failed: {res.status_code} → {res.json()}")
    except Exception as e:
        log(f"❌ Upload exception: {e}")

# Main process
if __name__ == "__main__":
    log(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")

    log("📦 Fetching prompts from Supabase...")
    response = supabase.table("prompts").select("id, prompt, brand").execute()

    if response.status_code == 200:
        prompts = response.data
        log(f"📦 Found {len(prompts)} prompts")

        for entry in prompts:
            prompt_id = entry['id']
            prompt_text = entry['prompt']
            brand = entry['brand']

            log(f"🧠 Evaluating prompt: '{prompt_text}' for brand: {brand}")
            result_text, position = evaluate_prompt(prompt_text, brand)

            if result_text:
                upload_result(prompt_id, result_text, position, brand, prompt_text)
    else:
        log(f"❌ Failed to fetch prompts: {response.status_code} → {response.json()}")

    log("✅ Done.")
