import os
import uuid
import datetime
import csv
import openai
from supabase import create_client, Client

# Attempt to load local .env if present (for local development environments)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is not installed or not needed in the automated environment
    pass

# Retrieve API keys and URLs from environment variables for flexibility in different environments
openai.api_key = os.getenv("OPENAI_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # Use your Supabase service role key

# Validate that required environment variables are set
if not openai.api_key:
    raise EnvironmentError("OpenAI API key not found in environment variables.")
if not supabase_url or not supabase_key:
    raise EnvironmentError("Supabase URL or service key not found in environment variables.")

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)
table_name = "prompt_results"  # Update this to your actual Supabase table name if different

# Read input prompts from CSV (assuming a CSV file provides prompt data)
input_file = "AI Rank Tracker - June.csv"
prompts = []
with open(input_file, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        prompts.append(row)

# Loop through each prompt entry and process it
for entry in prompts:
    prompt_id = entry.get("prompt_id")
    brand_id = entry.get("brand_id")
    brand_name = entry.get("brand_name")
    prompt_text = entry.get("prompt_text")

    # Skip this entry if any required field is missing
    if not (prompt_id and brand_id and brand_name and prompt_text):
        print(f"Skipping entry due to missing data: {entry}", flush=True)
        continue

    # Call the OpenAI API to get a response for the prompt
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0
        )
        answer_text = response["choices"][0]["message"]["content"].strip()
    except Exception as api_error:
        print(f"OpenAI API call failed for prompt_id {prompt_id}: {api_error}", flush=True)
        continue

    # Determine if the brand is mentioned in the AI response and find its position
    brand_mentioned = False
    position = 11  # default position = 11 (meaning "not found in top 10" by default)
    brand_lower = brand_name.lower()
    answer_lower = answer_text.lower()

    if brand_lower in answer_lower:
        # The brand name appears somewhere in the answer text.
        # Split the answer into lines for analysis (ignore empty lines).
        lines = [line.strip() for line in answer_text.splitlines() if line.strip() != ""]
        for line in lines:
            # Check if the line starts with a numeric rank (e.g., "1.", "2)", etc.)
            import re
            match = re.match(r'^(\d+)[\.\)]', line)
            if match:
                rank = int(match.group(1))
                if rank <= 10 and brand_lower in line.lower():
                    # Brand found within the top 10 list
                    brand_mentioned = True
                    position = rank
                    break
                elif rank > 10 and brand_lower in line.lower():
                    # Brand found but its rank is beyond 10
                    brand_mentioned = False
                    position = 11
                    break

    # DEBUG: Print the computed position for this prompt and brand (for logging/debugging purposes)
    print(f"Prompt ID {prompt_id} | Brand: '{brand_name}' | Computed position = {position}", flush=True)
    # FIX: The above print ensures the position value (including 11 or actual rank) is shown in logs for debugging.

    # Prepare the position value for database insertion
    position_to_upload = None if position == 11 else position
    if position == 11:
        # FIX: Convert position 11 to None to satisfy the database constraint (disallowing value 11 in position column)
        print(f"Position is 11 (brand not in top 10). Setting position to None for Supabase upload.", flush=True)

    # Prepare the data record to insert into Supabase
    result_id = str(uuid.uuid4())  # Generate a unique UUID for the result record
    run_date = datetime.date.today().isoformat()  # Current date in ISO format (YYYY-MM-DD)
    data_record = {
        "id": result_id,
        "prompt_id": prompt_id,
        "brand_id": brand_id,
        "ai_result": answer_text,
        "position": position_to_upload,
        "brand_mentioned": brand_mentioned,
        "run_date": run_date,
        "brand_name": brand_name,
        "prompt_text": prompt_text
    }

    # Insert the record into the Supabase table
    try:
        # Attempt the insertion and capture the response
        response = supabase.table(table_name).insert(data_record).execute()
        # Check for errors in the response
        if hasattr(response, "error") and response.error:
            # supabase-py may return an object with an 'error' attribute
            print(f"Supabase insert error for prompt_id {prompt_id}: {response.error}", flush=True)
        elif isinstance(response, dict) and response.get("error"):
            # In some versions, .execute() might return a dict with an 'error' key
            print(f"Supabase insert error for prompt_id {prompt_id}: {response.get('error')}", flush=True)
        else:
            # If no error, insertion was successful
            print(f"Inserted result for prompt_id {prompt_id} into Supabase successfully.", flush=True)
    except Exception as db_error:
        # Handle exceptions that may occur during the insert (e.g., network issues)
        print(f"Exception during Supabase insert for prompt_id {prompt_id}: {db_error}", flush=True)
