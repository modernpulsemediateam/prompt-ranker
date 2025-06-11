import os
import openai
import requests
import uuid
import hashlib
from datetime import datetime
from supabase import create_client, Client
import re

# 🔐 Load environment variables from GitHub Actions
client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BRAVE_API_KEY = os.environ["BRAVE_API_KEY"]

# 🌐 Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🌍 Brave API endpoint
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

def log(msg):
    print(msg, flush=True)

# 🔍 Get Brave results (with cache lookup)
def get_brave_results(query, count=5):
    query_hash = hashlib.md5(query.encode()).hexdigest()
    try:
        cache = supabase.table("brave_search_cache").select("results").eq("query_hash", query_hash).single().execute()
        if cache.data:
            log(f"✅ Cache hit for: {query}")
            return cache.data["results"]
    except:
        log(f"ℹ️ No cache for: {query}, calling Brave API")

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {"q": query, "count": count}
    try:
        response = requests.get(BRAVE_API_URL, headers=headers, params=params)
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])

        # 🧠 Save cache
        supabase.table("brave_search_cache").insert({
            "query_hash": query_hash,
            "query": query,
            "results": results,
            "cached_at": datetime.utcnow().isoformat()
        }).execute()

        return results
    except Exception as e:
        log(f"❌ Brave API error: {e}")
        return []

# 📄 Format results into string for GPT prompt
def format_search_results(results):
    formatted = []
    for i, r in enumerate(results):
        title = r.get("title", "")
        desc = r.get("description", "")
        url = r.get("url", "")
        formatted.append(f"{i+1}. {title} - {desc} ({url})")
    return "\n".join(formatted)

# 📊 Check GPT output for brand rank
def extract_position(text, brand):
    log(f"🔍 Parsing AI result for brand '{brand}'")
    for line in text.strip().splitlines():
        if match := re.match(r"(\d+)\.\s", line.strip()):
            num = int(match.group(1))
            if brand.lower() in line.lower():
                return str(num) if 1 <= num <= 10 else "Not Found"
    return "Not Found"

# 🧪 Evaluate a prompt using GPT-4o with Brave results
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
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.5,
            max_tokens=500
        )
        result_text = response.choices[0].message.content.strip()
        position = extract_position(result_text, brand)
        log(f"📈 '{brand}' rank: {position}")
        return result_text, position
    except Exception as e:
        log(f"❌ GPT error: {e}")
        return None, None

# ☁️ Upload result to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    try:
        is_ranked = position != "Not Found"
        supabase.table("prompt_results").insert({
            "id": str(uuid.uuid4()),
            "prompt_id": prompt_id,
            "ai_result": result_text,
            "position": position,
            "brand_mentioned": is_ranked,
            "run_date": datetime.utcnow().date().isoformat(),
            "brand_name": brand,
            "prompt_text": original_prompt,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        log(f"✅ Uploaded result for prompt: {original_prompt}")
    except Exception as e:
        log(f"❌ Upload error: {e}")

# 🚀 Run the pipeline for all prompts
if __name__ == "__main__":
    log(f"🚀 Running prompt ranker @ {datetime.utcnow().isoformat()}")
    response = supabase.table("prompts").select("id, prompt_text, brand_id").execute()
    if response.data:
        brands = supabase.table("brands").select("id, name").execute()
        brand_lookup = {b["id"]: b["name"] for b in brands.data} if brands.data else {}

        for p in response.data:
            prompt_id = p["id"]
            prompt_text = p["prompt_text"]
            brand_id = p["brand_id"]
            brand_name = brand_lookup.get(brand_id, "Unknown Brand")

            log(f"🧠 Evaluating: {prompt_text} → {brand_name}")
            result_text, position = evaluate_prompt(prompt_text, brand_name)
            if result_text:
                upload_result(prompt_id, result_text, position, brand_name, prompt_text)
                log("=" * 60)
    else:
        log("❌ No prompts found.")
