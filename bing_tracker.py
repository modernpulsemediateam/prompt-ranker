import requests
import uuid
import json
from datetime import datetime
from shared_utils import supabase, log, test_supabase_connection, get_brands_dict, get_prompts

# Get search results (using Brave as proxy for Bing)
def get_search_results(query, count=10):
    log(f"🔍 Searching for: '{query}'")
    
    # Using Brave API as a proxy for Bing results
    import os
    BRAVE_API_KEY = os.environ['BRAVE_API_KEY']
    
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
        
        log(f"🔍 Search API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('web', {}).get('results', [])
            log(f"🔍 Found {len(results)} search results")
            return results
        else:
            log(f"❌ Search API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        log(f"❌ Error calling Search API: {e}")
        return []

# Upload Bing search results to database
def upload_bing_results(prompt_text, brand_name, search_results):
    """Upload Bing search results to the bing_results table"""
    log(f"📤 Starting Bing upload for: '{prompt_text}' - Brand: {brand_name}")
    
    if not search_results:
        log(f"❌ No search results to upload for Bing")
        return False
    
    try:
        # Check if brand appears in search results
        brand_found_position = None
        found_result = None
        
        for i, result in enumerate(search_results, 1):
            title = result.get('title', '').lower()
            description = result.get('description', '').lower()
            url = result.get('url', '').lower()
            
            log(f"🔍 Bing check {i}: Looking for '{brand_name.lower()}' in title/desc/url")
            
            # Check if brand name appears in title, description, or URL
            if (brand_name.lower() in title or 
                brand_name.lower() in description or 
                brand_name.lower() in url):
                brand_found_position = i
                found_result = result
                log(f"✅ Found '{brand_name}' at position {i} in Bing results")
                break
        
        if not brand_found_position:
            log(f"❌ Brand '{brand_name}' not found in Bing results")
        
        # ALWAYS upload data, even if brand not found
        data = {
            "id": str(uuid.uuid4()),
            "brand_name": brand_name,
            "prompt_text": prompt_text,
            "position": brand_found_position,
            "url": found_result.get('url') if found_result else None,
            "title": found_result.get('title') if found_result else None,
            "description": found_result.get('description') if found_result else None,
            "run_date": datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        log(f"📤 Uploading Bing data: {json.dumps(data, indent=2)}")
        
        res = supabase.table("bing_results").insert(data).execute()
        if res.data:
            log(f"✅ Successfully uploaded Bing result - Position: {brand_found_position or 'Not Found'}")
            log(f"✅ Bing upload response data: {res.data}")
            return True
        else:
            log(f"❌ Bing upload failed - no data returned: {res}")
            return False
            
    except Exception as e:
        log(f"❌ Bing upload exception: {e}")
        import traceback
        log(f"❌ Bing traceback: {traceback.format_exc()}")
        return False

# Main Bing tracker process
if __name__ == "__main__":
    log(f"🚀 Bing Tracker Running @ {datetime.utcnow().isoformat()} UTC")

    # Test Supabase connection first
    if not test_supabase_connection():
        log("❌ Cannot proceed without Supabase connection")
        exit(1)

    # Get prompts and brands
    prompts = get_prompts()
    brands_dict = get_brands_dict()

    if prompts:
        for entry in prompts:
            prompt_text = entry['prompt_text']
            brand_id = entry['brand_id']
            brand_name = brands_dict.get(brand_id, "Unknown Brand")

            log(f"🔍 Processing Bing search for: '{prompt_text}' - Brand: {brand_name}")
            
            # Get search results
            search_results = get_search_results(prompt_text)
            
            if search_results:
                bing_success = upload_bing_results(prompt_text, brand_name, search_results)
                log(f"📊 Bing upload: {'✅ SUCCESS' if bing_success else '❌ FAILED'}")
            else:
                log(f"❌ No search results for '{prompt_text}' - skipping Bing upload")
                
            log("=" * 40)  # Separator between entries
    else:
        log("❌ No prompts found to process")

    log("✅ Bing Tracker Done.")
