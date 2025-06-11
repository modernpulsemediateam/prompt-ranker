import os
import openai
import requests
import uuid
from datetime import datetime
from supabase import create_client, Client
import re
import hashlib

# Set up OpenAI and Supabase
openai.api_key = os.environ['OPENAI_API_KEY']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
BRAVE_API_KEY = os.environ['BRAVE_API_KEY']  # ✅ Store this in GitHub as "BRAVE_API_KEY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

# Logging helper
def log(msg):
    print(msg, flush=True)

# Brave Search + Cache
def get_brave_results(query, count=5):
    query_hash = hashlib.md5(query.encode()).hexdigest()
    cache_table = "brave_search_cache"

    # Try to fetch from cache first
    log(f"🗂️ Checking cache for query: '{query}'")
    try:
        cache_response = supabase.table(cache_table).select("results").eq("query_hash", query_hash).single().execute()
        if cache_response.data:
            log(f"✅ Cache hit for query: '{query}'")
            return cache_response.data['results']
    except:
        log(f"🆕 No cache found for: '{query}', calling Brave Search")

    # Call Brave Search API if not cached
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {
        "q": query,
        "count": count
    }
    try:
        response = requests.get(BRAVE_API_URL, headers=headers, params=params)
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])

        # Cache the results
        supabase.table(cache_table).insert({
            "query_hash": query_hash,
            "query": query,
            "results": results,
            "cached_at": datetime.utcnow().isoformat()
        }).execute()

        return results
    except Exception as e:
        log(f"❌ Error fetching Brave search results: {e}")
        return []

# Format results for GPT
def format_search_results(results):
    formatted = []
    for i, result in enumerate(results):
        title = result.get("title", "")
        desc = result.get("description", "")
        url = result.get("url", "")
        formatted.append(f"{i+1}. {title} - {desc} ({url})")
    return "\n".join(formatted)

# Extract brand position
def extract_position(response_text, target_brand):
    log(f"🔍 Analyzing response for brand '{target_brand}':")
    log(f"🔍 Full AI response: {response_text[:200]}...")
    
    lines = response_text.strip().splitlines()
    for line in lines:
        match = re.match(r"(\d+)\.\s", line.strip())
        if match:
            num = int(match.group(1))
            log(f"🔍 Found numbered line {num}: {line.strip()}")
            if target_brand.lower() in line.lower():
                log(f"🔍 Brand '{target_brand}' found at position {num}")
                return str(num) if 1 <= num <= 10 else "Not Found"
    log(f"🔍 Brand '{target_brand}' not found in any numbered position")
    return "Not Found"

# Evaluate prompt
def evaluate_prompt(prompt, brand):
    brave_results = get_brave_results(prompt)
    search_context = format_search_results(brave_results)
    
    full_prompt = f"""A user searched for: '{prompt}'

Here are the top real-time web results:
{search_context}

Now, based on the query and these results, rank the most relevant businesses or websites.
Does '{brand}' appear? Include them if they are relevant.
"""
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

# Upload result to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    log(f"📤 Uploading result for: {original_prompt}")
    try:
        is_ranked = position != "Not Found" and position is not None
        brand_mentioned = is_ranked
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
        res = supabase.table("prompt_results").insert(data).execute()
        if res.data:
            log(f"✅ Uploaded result: {data}")
        else:
            log(f"❌ Upload failed: {res}")
    except Exception as e:
        log(f"❌ Upload exception: {e}")

# Main loop
if __name__ == "__main__":
    log(f"🚀 Running @ {datetime.utcnow().isoformat()} UTC")
    response = supabase.table("prompts").select("id, prompt_text, brand_id").execute()

    if response.data:
        prompts = response.data
        brands_response = supabase.table("brands").select("id, name").execute()
        brands_dict = {b['id']: b['name'] for b in brands_response.data} if brands_response.data else {}

        for entry in prompts:
            prompt_id = entry['id']
            prompt_text = entry['prompt_text']
            brand_id = entry['brand_id']
            brand_name = brands_dict.get(brand_id, "Unknown Brand")

            log(f"🧠 Evaluating prompt: '{prompt_text}' for brand: {brand_name}")
            result_text, position = evaluate_prompt(prompt_text, brand_name)
            if result_text:
                upload_result(prompt_id, result_text, position, brand_name, prompt_text)
                log("=" * 80)
    else:
        log(f"❌ Failed to fetch prompts from Supabase")

    log("✅ Done.")
