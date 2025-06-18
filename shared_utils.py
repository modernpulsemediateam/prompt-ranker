from dotenv import load_dotenv
import os
import uuid
from datetime import datetime
from supabase import create_client, Client

load_dotenv()

# Set up Supabase - handle environment variables properly
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Validate environment variables
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is not set")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is not set")

# Strip any whitespace that might have been added
SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_KEY = SUPABASE_KEY.strip()

# Debug logging to help troubleshoot
print(f"🔍 SUPABASE_URL: {SUPABASE_URL}")
print(f"🔍 SUPABASE_URL length: {len(SUPABASE_URL)}")

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
    response = supabase.table("prompts").select("id, prompt_text, brand_id, location").execute()
    if response.data:
        log(f"📦 Found {len(response.data)} prompts")
        return response.data
    else:
        log(f"❌ Failed to fetch prompts: {response}")
        return []
