from openai import OpenAI

client = OpenAI(api_key=openai.api_key)

def evaluate_prompt(prompt_id, prompt_text, brand_id, brand_name):
    print(f"🧠 Evaluating: {prompt_text}")
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_text}],
        )

        result_text = response.choices[0].message.content
        mentioned = brand_name.lower() in result_text.lower()
        position = 1 if mentioned else 11

        payload = {
            "prompt_id": prompt_id,
            "brand_id": brand_id,
            "ai_result": result_text,
            "position": position,
            "brand_mentioned": mentioned,
        }

        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/prompt_results",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        )

        if res.status_code == 201:
            print(f"✅ Uploaded result for: {prompt_text}")
        else:
            print(f"❌ Upload failed: {res.status_code} → {res.text}")

    except Exception as e:
        print(f"⚠️ Error for prompt '{prompt_text}': {e}")
