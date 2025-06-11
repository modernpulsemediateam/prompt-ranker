
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

# Extract position from AI response (1–10 only, else "Not Found")
def extract_position(response_text, target_brand):
    log(f"🔍 Analyzing response for brand '{target_brand}':")
    log(f"🔍 Full AI response: {response_text[:200]}...")
    
    lines = response_text.strip().splitlines()
    for line in lines:
        match = re.match(r"(\d+)\.\s", line.strip())
        if match:
            num = int(match.group(1))
            log(f"🔍 Found numbered line {num}: {line.strip()}")
            
            # Check if this line mentions the target brand
            if target_brand.lower() in line.lower():
                log(f"🔍 Brand '{target_brand}' found at position {num}")
                if 1 <= num <= 10:
                    log(f"🔍 Position {num} is valid (1-10), returning: {str(num)}")
                    return str(num)  # Return as string for positions 1-10
                else:
                    # Found the brand but it's at position 11+ - return "Not Found"
                    log(f"🔍 Position {num} is >10, converting to 'Not Found'")
                    return "Not Found"
    
    # Brand not found at all in any numbered list
    log(f"🔍 Brand '{target_brand}' not found in any numbered position")
    return "Not Found"

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
        log(f"🔍 Final position determined: '{position}' (type: {type(position)})")
        return result_text, position
    except Exception as e:
        log(f"❌ Error evaluating prompt '{prompt}': {e}")
        return None, None

# Upload results to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    log(f"📤 About to upload to Supabase:")
    log(f"📤 Position value: '{position}' (type: {type(position)})")
    log(f"📤 Position == 'Not Found': {position == 'Not Found'}")
    log(f"📤 Position != 'Not Found': {position != 'Not Found'}")
    
    try:
        # Convert position to determine success and brand_mentioned
        is_ranked = position != "Not Found" and position is not None
        brand_mentioned = is_ranked
        
        log(f"📤 is_ranked: {is_ranked}")
        log(f"📤 brand_mentioned: {brand_mentioned}")
        
        data = {
            "id": str(uuid.uuid4()),
            "prompt_id": prompt_id,
            "ai_result": result_text,
            "position": position,
            "brand_mentioned": brand_mentioned,
            "run_date": datetime.utcnow().date().isoformat(),
            "brand_name": brand,
            "prompt_text": original_prompt,
            "created_at": datetime.utcnow().isoformat()
        }
        
        log(f"📤 Final data being sent to Supabase: {data}")
        
        res = supabase.table("prompt_results").insert(data).execute()
        if res.data:
            log(f"✅ Uploaded result for: '{original_prompt}' - Position: {position}")
            log(f"✅ Supabase response: {res.data}")
        else:
            log(f"❌ Upload failed: {res}")
    except Exception as e:
        log(f"❌ Upload exception: {e}")

# Main process
if __name__ == "__main__":
    log(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")

    log("📦 Fetching prompts from Supabase...")
    response = supabase.table("prompts").select("id, prompt_text, brand_id").execute()

    if response.data:
        prompts = response.data
        log(f"📦 Found {len(prompts)} prompts")

        # Fetch brands to get brand names
        brands_response = supabase.table("brands").select("id, name").execute()
        brands_dict = {brand['id']: brand['name'] for brand in brands_response.data} if brands_response.data else {}

        for entry in prompts:
            prompt_id = entry['id']
            prompt_text = entry['prompt_text']
            brand_id = entry['brand_id']
            brand_name = brands_dict.get(brand_id, "Unknown Brand")

            log(f"🧠 Evaluating prompt: '{prompt_text}' for brand: {brand_name}")
            result_text, position = evaluate_prompt(prompt_text, brand_name)

            if result_text:
                upload_result(prompt_id, result_text, position, brand_name, prompt_text)
                log("=" * 80)  # Separator between entries
    else:
        log(f"❌ Failed to fetch prompts: {response}")

    log("✅ Done.")
