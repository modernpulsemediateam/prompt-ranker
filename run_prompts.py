
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

# ... keep existing code (upload_result function and main process)
</lov-write>
