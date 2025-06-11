
import os
import openai
import requests
import uuid
from datetime import datetime
from supabase import create_client, Client
import re
import json

# Set up OpenAI and Supabase
client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
BRAVE_API_KEY = os.environ['BRAVE_API_KEY']
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Logging helper
def log(msg):
    print(msg, flush=True)

# Get real search results from Brave Search API
def get_brave_search_results(query, count=10):
    log(f"🔍 Searching Brave for: '{query}'")
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    
    params = {
        "q": query,
        "count": count,
        "search_lang": "en",
        "country": "US",
        "safesearch": "moderate",
        "text_decorations": "false",
        "spellcheck": "true"
    }
    
    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('web', {}).get('results', [])
            log(f"🔍 Found {len(results)} search results from Brave")
            return results
        else:
            log(f"❌ Brave API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        log(f"❌ Error calling Brave API: {e}")
        return []

# Format search results for AI analysis
def format_search_results_for_ai(search_results):
    formatted_results = []
    for i, result in enumerate(search_results, 1):
        formatted_result = f"{i}. {result.get('title', 'No title')}\n"
        formatted_result += f"   URL: {result.get('url', 'No URL')}\n"
        formatted_result += f"   Description: {result.get('description', 'No description')}\n"
        formatted_results.append(formatted_result)
    
    return "\n".join(formatted_results)

# Extract position from AI response (1–10 only, else "Not Found")
def extract_position(response_text, target_brand):
    log(f"🔍 Analyzing AI response for brand '{target_brand}':")
    log(f"🔍 AI response excerpt: {response_text[:300]}...")
    
    lines = response_text.strip().splitlines()
    for line in lines:
        # Look for numbered positions in the analysis
        match = re.search(r"position\s*(\d+)", line.lower())
        if match:
            position = int(match.group(1))
            if target_brand.lower() in line.lower():
                log(f"🔍 Brand '{target_brand}' found at position {position}")
                if 1 <= position <= 10:
                    return str(position)
                else:
                    return "Not Found"
        
        # Also check for direct numbered list format
        match = re.match(r"(\d+)\.\s", line.strip())
        if match:
            num = int(match.group(1))
            if target_brand.lower() in line.lower() and 1 <= num <= 10:
                log(f"🔍 Brand '{target_brand}' found at position {num}")
                return str(num)
    
    # Check if brand is mentioned but no position found
    if target_brand.lower() in response_text.lower():
        log(f"🔍 Brand '{target_brand}' mentioned but no clear position found")
        return "Not Found"
    
    log(f"🔍 Brand '{target_brand}' not found in search results")
    return "Not Found"

# Evaluate a single prompt using real search data
def evaluate_prompt(prompt, brand):
    log(f"🔍 Getting real search results for: '{prompt}'")
    
    # Get real search results from Brave
    search_results = get_brave_search_results(prompt)
    
    if not search_results:
        log(f"❌ No search results found for '{prompt}'")
        return None, None
    
    # Format results for AI analysis
    formatted_results = format_search_results_for_ai(search_results)
    
    # Create prompt for AI analysis
    analysis_prompt = f"""You are analyzing real search results to determine brand positioning.

Search Query: "{prompt}"
Target Brand: "{brand}"

Here are the actual search results from Brave Search:

{formatted_results}

Please analyze these results and determine:
1. If the brand "{brand}" appears in any of these search results
2. If yes, what position (1-10) it appears at based on the numbered list above
3. Provide a brief analysis of the brand's visibility for this search query

Be specific about the position number if the brand is found."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a search result analyst. Analyze the provided search results and determine brand positioning accurately."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )
        result_text = response.choices[0].message.content.strip()
        position = extract_position(result_text, brand)
        log(f"🔍 Final position determined: '{position}' (type: {type(position)})")
        return result_text, position
    except Exception as e:
        log(f"❌ Error analyzing search results for '{prompt}': {e}")
        return None, None

# Upload results to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    log(f"📤 About to upload to Supabase:")
    log(f"📤 Position value: '{position}' (type: {type(position)})")
    
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
</lov-write>
