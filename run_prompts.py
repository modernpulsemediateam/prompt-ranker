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

# Upload Google search results to database
def upload_google_results(prompt_text, brand_name, search_results):
    """Upload Google search results to the google_results table"""
    log(f"📤 Uploading Google results for: '{prompt_text}' - Brand: {brand_name}")
    
    try:
        # Check if brand appears in search results
        brand_found_position = None
        
        for i, result in enumerate(search_results, 1):
            title = result.get('title', '').lower()
            description = result.get('description', '').lower()
            url = result.get('url', '').lower()
            
            # Check if brand name appears in title, description, or URL
            if (brand_name.lower() in title or 
                brand_name.lower() in description or 
                brand_name.lower() in url):
                brand_found_position = i
                break
        
        # Upload the brand's result if found, or mark as not found
        data = {
            "id": str(uuid.uuid4()),
            "brand_name": brand_name,
            "prompt_text": prompt_text,
            "position": brand_found_position,
            "url": search_results[brand_found_position - 1].get('url') if brand_found_position else None,
            "title": search_results[brand_found_position - 1].get('title') if brand_found_position else None,
            "description": search_results[brand_found_position - 1].get('description') if brand_found_position else None,
            "run_date": datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        res = supabase.table("google_results").insert(data).execute()
        if res.data:
            log(f"✅ Uploaded Google result - Position: {brand_found_position or 'Not Found'}")
        else:
            log(f"❌ Google upload failed: {res}")
            
    except Exception as e:
        log(f"❌ Google upload exception: {e}")

# Upload Bing search results to database
def upload_bing_results(prompt_text, brand_name, search_results):
    """Upload Bing search results to the bing_results table"""
    log(f"📤 Uploading Bing results for: '{prompt_text}' - Brand: {brand_name}")
    
    try:
        # Check if brand appears in search results
        brand_found_position = None
        
        for i, result in enumerate(search_results, 1):
            title = result.get('title', '').lower()
            description = result.get('description', '').lower()
            url = result.get('url', '').lower()
            
            # Check if brand name appears in title, description, or URL
            if (brand_name.lower() in title or 
                brand_name.lower() in description or 
                brand_name.lower() in url):
                brand_found_position = i
                break
        
        # Upload the brand's result if found, or mark as not found
        data = {
            "id": str(uuid.uuid4()),
            "brand_name": brand_name,
            "prompt_text": prompt_text,
            "position": brand_found_position,
            "url": search_results[brand_found_position - 1].get('url') if brand_found_position else None,
            "title": search_results[brand_found_position - 1].get('title') if brand_found_position else None,
            "description": search_results[brand_found_position - 1].get('description') if brand_found_position else None,
            "run_date": datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        res = supabase.table("bing_results").insert(data).execute()
        if res.data:
            log(f"✅ Uploaded Bing result - Position: {brand_found_position or 'Not Found'}")
        else:
            log(f"❌ Bing upload failed: {res}")
            
    except Exception as e:
        log(f"❌ Bing upload exception: {e}")

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
    for line_num, line in enumerate(lines, 1):
        # Look for numbered list format (1., 2., etc.)
        match = re.match(r"(\d+)\.\s*(.+)", line.strip())
        if match:
            position = int(match.group(1))
            company_info = match.group(2).lower()
            
            # Check if target brand is mentioned in this ranked position
            if target_brand.lower() in company_info:
                if 1 <= position <= 10:
                    log(f"🔍 Brand '{target_brand}' found at position {position}")
                    return str(position)
                else:
                    log(f"🔍 Brand '{target_brand}' found but at position {position} (>10), marking as Not Found")
                    return "Not Found"
    
    # Check if brand is mentioned but no position found
    if target_brand.lower() in response_text.lower():
        log(f"🔍 Brand '{target_brand}' mentioned but no clear ranking position found")
        return "Not Found"
    
    log(f"🔍 Brand '{target_brand}' not found in AI ranking")
    return "Not Found"

# Evaluate a single prompt using real search data
def evaluate_prompt(prompt, brand):
    log(f"🔍 Getting real search results for: '{prompt}'")
    
    # Get real search results from Brave
    search_results = get_brave_search_results(prompt)
    
    if not search_results:
        log(f"❌ No search results found for '{prompt}'")
        return None, None
    
    # Upload to Google and Bing tables (using Brave data as proxy for both)
    upload_google_results(prompt, brand, search_results)
    upload_bing_results(prompt, brand, search_results)
    
    # Format results for AI analysis
    formatted_results = format_search_results_for_ai(search_results)
    
    # Create ChatGPT-style prompt for AI analysis
    analysis_prompt = f"""Based on the search results below, please list the top companies/brands for the keyword "{prompt}". 

Here are the current search results:

{formatted_results}

Your task is to:
1. Analyze these search results
2. Rank the top companies/brands mentioned for this keyword in order of relevance and authority
3. Provide a numbered list (1-10) of the best companies for "{prompt}" based on these results
4. Focus on actual companies/brands, not just informational websites

Please respond with a clear numbered list format like:
1. Company Name - brief reason
2. Company Name - brief reason
etc.

Target brand to pay special attention to: {brand}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert business analyst who ranks companies based on search results. Provide clear, numbered rankings of the top companies for any given keyword."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        result_text = response.choices[0].message.content.strip()
        position = extract_position(result_text, brand)
        log(f"🔍 Final position determined: '{position}' (type: {type(position)})")
        return result_text, position
    except Exception as e:
        log(f"❌ Error analyzing search results for '{prompt}': {e}")
        return None, None

# Upload AI results to Supabase
def upload_result(prompt_id, result_text, position, brand, original_prompt):
    log(f"📤 About to upload AI result to Supabase:")
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
            "tracking_type": "ai",  # Mark as AI tracking
            "created_at": datetime.utcnow().isoformat()
        }
        
        log(f"📤 Final AI data being sent to Supabase: {data}")
        
        res = supabase.table("prompt_results").insert(data).execute()
        if res.data:
            log(f"✅ Uploaded AI result for: '{original_prompt}' - Position: {position}")
            log(f"✅ Supabase response: {res.data}")
        else:
            log(f"❌ AI upload failed: {res}")
    except Exception as e:
        log(f"❌ AI upload exception: {e}")

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
