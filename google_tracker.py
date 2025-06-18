import requests
import uuid
import json
from datetime import datetime
from shared_utils import supabase, log, test_supabase_connection, get_brands_dict, get_prompts
import os
from urllib.parse import urlparse

# --- ENV Setup for SerpAPI ---
def get_serpapi_key():
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        log("❌ Missing SERPAPI_KEY.")
    return api_key

# Extract root domain from URL
def extract_simple_domain(url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""

# Get brand domains from Supabase
def get_brand_domains():
    domain_map = {}
    try:
        response = supabase.table("brands").select("name,url").execute()
        if response.data:
            for row in response.data:
                name = row.get("name")
                url = row.get("url", "")
                if name and url:
                    domain = extract_simple_domain(url)
                    if domain:
                        domain_map[name] = domain
        log(f"📦 Brand domains loaded: {domain_map}")
    except Exception as e:
        log(f"❌ Failed to load brand domains: {e}")
    return domain_map

# --- SerpAPI implementation ---
def get_search_results(query, max_results=100, location=None):
    api_key = get_serpapi_key()
    if not api_key:
        log("❌ Missing SerpAPI key. Please check SERPAPI_KEY environment variable.")
        return []

    log(f"🔍 Searching via SerpAPI for: '{query}'")
    
    # Use provided location or default to United States
    if not location:
        location = "United States"
    
    log(f"🌍 Using location: {location}")

    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": "us",
        "num": min(max_results, 100),
        "device": "desktop"
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        log(f"📡 SerpAPI response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            log(f"📊 SerpAPI returned data keys: {list(data.keys())}")
            
            organic_results = data.get("organic_results", [])
            log(f"📊 Found {len(organic_results)} organic search results")
            
            results = []
            for i, result in enumerate(organic_results[:max_results]):
                position = i + 1
                results.append({
                    "position": position,
                    "title": result.get("title", ""),
                    "url": result.get("link", ""),
                    "description": result.get("snippet", "")
                })
            
            log(f"🎯 Total search results processed: {len(results)}")
            return results
        else:
            log(f"❌ SerpAPI error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        log(f"❌ SerpAPI exception: {e}")
        return []

# Find domain match
def find_brand_position(brand_name, search_results, brand_domains):
    target_domain = brand_domains.get(brand_name)
    if not target_domain:
        log(f"⚠️ No domain found for brand: {brand_name}")
        return False, None

    log(f"🔍 Looking for domain '{target_domain}' in {len(search_results)} results")
    for result in search_results:
        result_domain = extract_simple_domain(result.get("url", ""))
        if target_domain == result_domain:
            log(f"✅ Found domain '{target_domain}' at position {result.get('position')}")
            return True, result.get('position')

    log(f"❌ Domain '{target_domain}' not found in search results")
    return False, None

# Format for DB
def format_rank_results(search_results):
    formatted_results = []
    for result in search_results[:50]:
        formatted_results.append({
            "position": result.get("position"),
            "title": result.get("title", ""),
            "description": result.get("description", ""),
            "url": result.get("url", "")
        })
    return json.dumps(formatted_results)

# Upload to Supabase
def upload_google_results(prompt_text, brand_name, search_results, brand_domains, location=None):
    if not search_results:
        log(f"❌ No search results to upload for prompt: {prompt_text}")
        return False

    try:
        log("🔍 Starting upload process...")
        
        # Log the first few search results for debugging
        log(f"🔍 First 3 search results for debugging:")
        for i, result in enumerate(search_results[:3]):
            log(f"  {i+1}. {result.get('title', 'No title')} - {result.get('url', 'No URL')}")
        
        brand_mentioned, position = find_brand_position(brand_name, search_results, brand_domains)
        log(f"🔍 Brand position found: {position if position is not None else 'Not found'}")
        
        rank_results_data = format_rank_results(search_results)
        top_result = search_results[0] if search_results else {}

        # Handle position conversion
        position_value = position if position is not None else None
        
        data = {
            "id": str(uuid.uuid4()),
            "brand_name": brand_name,
            "prompt_text": prompt_text[:500],  # Limit length to avoid database errors
            "position": position_value,
            "url": top_result.get('url', '')[:500],
            "title": top_result.get('title', '')[:200],
            "description": top_result.get('description', '')[:1000],
            "brand_mentioned": brand_mentioned,
            "rank_results": rank_results_data,
            "run_date": datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "location": str(location)[:100] if location else None
        }

        log("📋 Data prepared for upload:")
        for key, value in data.items():
            if key != 'rank_results':  # Don't log the full results to keep logs clean
                log(f"   {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        log("🚀 Attempting to insert into Supabase...")
        res = supabase.table("google_results").insert(data).execute()
        
        log(f"📡 Supabase response status code: {getattr(res, 'status_code', 'N/A')}")
        
        if hasattr(res, 'error') and res.error:
            log(f"❌ Supabase error: {res.error}")
            if hasattr(res.error, 'message'):
                log(f"❌ Error message: {res.error.message}")
            if hasattr(res.error, 'details'):
                log(f"❌ Error details: {res.error.details}")
            return False
            
        if hasattr(res, 'data') and res.data and len(res.data) > 0:
            log(f"✅ Successfully uploaded result for {brand_name} (ID: {res.data[0].get('id', 'unknown')})")
            return True
        else:
            log(f"❌ No data returned from Supabase. Full response: {res}")
            log(f"❌ Response attributes: {dir(res)}")
            if hasattr(res, 'data'):
                log(f"❌ Response data type: {type(res.data).__name__}")
                log(f"❌ Response data: {res.data}")
            return False
            
    except Exception as e:
        log(f"❌ Exception in upload_google_results: {type(e).__name__}: {str(e)}")
        import traceback
        log(f"❌ Full traceback: {traceback.format_exc()}")
        return False

# Main entry
if __name__ == "__main__":
    log(f"🚀 SerpAPI Rank Tracker Running @ {datetime.utcnow().isoformat()} UTC")

    if not test_supabase_connection():
        log("❌ Cannot proceed without Supabase connection")
        exit(1)

    api_key = get_serpapi_key()
    if not api_key:
        log("❌ Missing SerpAPI key. Please check SERPAPI_KEY environment variable.")
        exit(1)

    brand_domains = get_brand_domains()
    if not brand_domains:
        log("❌ No brand domains found. Please check your brands table has URLs.")
        exit(1)

    prompts = get_prompts()
    log(f"🔍 Retrieved {len(prompts)} prompts from database")
    for i, p in enumerate(prompts[:3]):  # Show first 3 prompts as sample
        log(f"  {i+1}. ID: {p.get('id')}, Text: {p.get('prompt_text')}, Location: {p.get('location')}")

    brands_dict = get_brands_dict()

    if prompts:
        log(f"🎯 Processing {len(prompts)} prompts")
        processed_count = 0
        success_count = 0
        
        for entry in prompts:
            prompt_text = entry['prompt_text']
            brand_id = entry['brand_id']
            brand_name = brands_dict.get(brand_id, "Unknown Brand")
            location = entry.get('location')

            log(f"📝 Processing prompt {processed_count + 1}/{len(prompts)}: '{prompt_text[:50]}...' for brand '{brand_name}'")
            if location:
                log(f"🌍 Using location from prompt: {location}")

            search_results = get_search_results(prompt_text, max_results=100, location=location)
            if search_results:
                success = upload_google_results(
                    prompt_text=prompt_text,
                    brand_name=brand_name,
                    search_results=search_results,
                    brand_domains=brand_domains,
                    location=location
                )
                if success:
                    success_count += 1
                else:
                    log(f"❌ Failed to upload results for prompt: {prompt_text}")
            else:
                log(f"❌ No search results for prompt: {prompt_text}")
            
            processed_count += 1

        log(f"📊 Processing complete: {success_count}/{processed_count} prompts successfully uploaded to database")
    else:
        log("❌ No prompts found to process")

    log("✅ SerpAPI Rank Tracker Done.")
