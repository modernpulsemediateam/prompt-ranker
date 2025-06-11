import os
import uuid
import openai
import requests
from datetime import datetime
from supabase import create_client, Client

# Init
openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")

# Fetch prompts
print("📦 Fetching prompts from Supabase...")
response = supabase.table("prompts").select("*").execute()
if response.status_code != 200:
    raise Exception(f"❌ Failed to fetch prompts: {response.status_code}")
prompts = response.data
print(f"📦 Found {len(prompts)} prompts")

# Eval function
def evaluate_prompt(prompt_text):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Return a numbered list of companies."},
            {"role": "user", "content": prompt_text},
        ],
        temperature=0.2,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()

# Parse position
def extract_position(response_text):
    lines = response_text.strip().splitlines()
    for line in lines:
        if line.strip().startswith("1."):
            return 1
        if line.strip().startswith("2."):
            return 2
        if line.strip().startswith("3."):
            return 3
        if line.strip().startswith("4."):
            return 4
        if line.strip().startswith("5."):
            return 5
        if line.strip().startswith("6."):
            return 6
        if line.strip().startswith("7."):
            return 7
        if line.strip().startswith("8."):
            return 8
        if line.strip().startswith("9."):
            return 9
        if line.strip().startswith("10."):
            return 10
    return None  # If not in top 10, don't assign 11

# Run eval
for prompt in prompts:
    prompt_id = prompt["id"]
    text = prompt["prompt"]
    brand = prompt.get("brand", "")
    print(f"🧠 Evaluating prompt: '{text}' for brand: {brand}")

    try:
        answer = evaluate_prompt(text)
        position = extract_position(answer)

        print(f"🔢 Parsed position: {position if position is not None else 'None'}")

        data = {
            "id": str(uuid.uuid4()),
            "prompt_id": prompt_id,
            "user_id": prompt.get("user_id", "00000000-0000-0000-0000-000000000001"),
            "response": answer,
            "position": position,  # Will be null if not in top 10
            "is_competitor": False,
            "date": datetime.utcnow().date().isoformat(),
            "brand": brand,
            "query": text,
            "created_at": datetime.utcnow().isoformat()
        }

        result = supabase.table("prompt_results").insert(data).execute()

        if result.status_code == 201:
            print(f"✅ Uploaded result for: '{text}'")
        else:
            print(f"❌ Upload failed: {result.status_code} → {result.data}")

    except Exception as e:
        print(f"❌ Error evaluating prompt: {e}")

print("✅ Done.")
