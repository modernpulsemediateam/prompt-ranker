#!/usr/bin/env python3
"""
Bing rank-tracker via SerpApi (SDK-free).

• Reads prompts (brand_id, prompt_text, location) from Supabase
• Reads brands (id, name, domain) from Supabase
• Queries SerpApi’s Bing JSON endpoint with plain `requests`
• Uploads results to `bing_results` table
"""

import os, json, uuid, requests
from datetime import datetime, timezone
from urllib.parse import urlparse

from shared_utils import (
    supabase,
    log,
    test_supabase_connection,
    get_prompts          # -> list of dicts with keys brand_id, prompt_text, location
)

# ─────────────────────────── SerpApi config ──────────────────────────
SERP_ENDPOINT = "https://serpapi.com/search.json"
API_KEY = os.getenv("SERPAPI_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("SERPAPI_KEY environment variable is missing")

# ─────────────────────── brand helpers (Option B) ─────────────────────
def get_brands_dict() -> dict[int, dict]:
    """Return {brand_id: {'name': str, 'domain': str|None}} from Supabase."""
    log("📦 Fetching brands (id, name, url) from Supabase…")
    resp = supabase.table("brands").select("id,name,url").execute()
    # The response object has a 'data' attribute, not a dict
    data = resp.data or []
    mapping = {
        row["id"]: {"name": row["name"], "domain": (row.get("url") or None)}
        for row in data
    }
    log(f"📦 Found {len(mapping)} brands")
    return mapping

def simple_domain(url_or_domain: str) -> str:
    """Return bare domain (strip scheme/www)."""
    try:
        if not url_or_domain.startswith(("http://", "https://")):
            url_or_domain = "https://" + url_or_domain
        dom = urlparse(url_or_domain).netloc.lower()
        return dom[4:] if dom.startswith("www.") else dom
    except Exception:
        return url_or_domain.lower()

def find_brand_position(results: list[dict], brand_domain: str) -> tuple[bool, int | None]:
    brand_domain = simple_domain(brand_domain)
    for r in results:
        res_dom = simple_domain(r.get("url", ""))
        if res_dom == brand_domain or res_dom.endswith("." + brand_domain):
            return True, r["position"]
    return False, None

# ───────────────────────────── Bing search ────────────────────────────
def bing_search(query: str, location: str | None, max_results: int = 50) -> list[dict]:
    """Call SerpApi’s Bing engine and return a list of simplified results."""
    params = {
        "engine": "bing",
        "q": query,
        "api_key": API_KEY,
        "device": "desktop",
        "count": max_results,
    }
    if location:                 # ← exactly the string stored in Supabase
        params["location"] = location

    resp = requests.get(SERP_ENDPOINT, params=params, timeout=45)
    resp.raise_for_status()
    raw = resp.json().get("organic_results") or []

    return [
        {
            "position": idx,
            "title": item.get("title") or item.get("name", ""),
            "url": item.get("link") or item.get("url", ""),
            "description": item.get("snippet") or item.get("description", "")
        }
        for idx, item in enumerate(raw[:max_results], 1)
    ]

# ───────────────────────────── upload row ─────────────────────────────
def upload_row(prompt_row: dict, brand_meta: dict, results: list[dict]):
    mentioned, pos = find_brand_position(results, brand_meta["domain"])
    payload = {
        "id": str(uuid.uuid4()),
        "prompt_text": prompt_row["prompt_text"],
        "brand_name":  brand_meta["name"],
        "position":    pos,
        "brand_mentioned": mentioned,
        "url":        results[0]["url"] if results else "",
        "title":      results[0]["title"] if results else "",
        "description":results[0]["description"] if results else "",
        "rank_results": json.dumps(results),
        "run_date":   datetime.now(timezone.utc).date().isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "location":   prompt_row.get("location"),
    }
    supabase.table("bing_results").insert(payload).execute()
    log(f"✅ Uploaded | {brand_meta['name']} | pos={pos or 'n/a'}")

# ─────────────────────────────── main ────────────────────────────────
if __name__ == "__main__":
    log("🚀 Bing rank-tracker starting")
    test_supabase_connection()

    prompts      = get_prompts()
    brands_by_id = get_brands_dict()
    log(f"📦 Found {len(prompts)} prompts")

    for idx, p in enumerate(prompts, 1):
        brand_meta = brands_by_id.get(p["brand_id"])
        if not brand_meta or not brand_meta["domain"]:
            log(f"⚠ [{idx}/{len(prompts)}] Skipped—no domain for brand_id={p['brand_id']}")
            continue

        log(f"[{idx}/{len(prompts)}] '{p['prompt_text'][:40]}…' | brand={brand_meta['name']} | loc={p.get('location')}")
        results = bing_search(p["prompt_text"], p.get("location"))
        upload_row(p, brand_meta, results)

    log("🏁 Bing tracking done")
