for prompt in prompts:
    prompt_text = prompt["prompt_text"]
    brand_id = prompt["brand_id"]
    prompt_id = prompt["id"]
    brand_name = prompt.get("brand", {}).get("name", "Unknown")

    print(f"🧠 Evaluating prompt: {prompt_text} for brand: {brand_name}")

    result = run_prompt(prompt_text)
    if result:
        if brand_name.lower() in result.lower():
            position = 1
        else:
            position = "Not Found"  # << this is the fix
        upload_result(prompt_id, brand_id, prompt_text, result, position)
