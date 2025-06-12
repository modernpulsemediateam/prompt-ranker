import os
import uuid
from datetime import datetime
from supabase import create_client, Client

# Set up Supabase
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Logging helper
def log(msg):
    print(msg, flush=True)

# Test Supabase connection
def test_supabase_connection():
    log("🔗 Testing Supabase connection...")
    try:
        # Test connection by attempting to read from brands table
        response = supabase.table("brands").select("id").limit(1).execute()
        log(f"✅ Supabase connection successful. Response: {response}")
        return True
    except Exception as e:
        log(f"❌ Supabase connection failed: {e}")
        return False

# Get brands dictionary
def get_brands_dict():
    log("📦 Fetching brands from Supabase...")
    brands_response = supabase.table("brands").select("id, name").execute()
    brands_dict = {brand['id']: brand['name'] for brand in brands_response.data} if brands_response.data else {}
    log(f"📦 Found {len(brands_dict)} brands")
    return brands_dict

# Get prompts
def get_prompts():
    log("📦 Fetching prompts from Supabase...")
    response = supabase.table("prompts").select("id, prompt_text, brand_id").execute()
    if response.data:
        log(f"📦 Found {len(response.data)} prompts")
        return response.data
    else:
        log(f"❌ Failed to fetch prompts: {response}")
        return []
