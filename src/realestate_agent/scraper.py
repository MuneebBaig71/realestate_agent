"""
scraper.py — Bright Data scraping layer for the property agent.

Flow:
  1. Bright Data Web Unlocker fetches a portal search-results page (gets past anti-bot).
  2. Page content is reduced to text to keep token use sane.
  3. The AIML LLM extracts clean, structured listings as JSON.

Required env vars:
  BRIGHTDATA_API_TOKEN  - from Bright Data control panel (API keys page)
  OPENAI_API_KEY        - your AIML API key (the var your app already uses)
"""

import os
import json
from dotenv import load_dotenv, find_dotenv, dotenv_values

# Load environment variables from a .env file if present and ensure values
# from the file are available via os.environ for the rest of the script.
_dotenv_path = find_dotenv()
if _dotenv_path:
    load_dotenv(_dotenv_path)
    for _k, _v in dotenv_values(_dotenv_path).items():
        if _v is not None and _k not in os.environ:
            os.environ[_k] = _v
else:
    # fallback: attempt default locations (project root / current dir)
    load_dotenv()
import requests
from openai import OpenAI

# Optional: lighter token use if bs4 is installed; falls back to raw if not.
try:
    import importlib

    _bs4 = importlib.import_module("bs4")
    BeautifulSoup = _bs4.BeautifulSoup
    _HAS_BS4 = True
except Exception:
    BeautifulSoup = None
    _HAS_BS4 = False

AIML_MODEL = "gpt-4o-mini"      # if AIML rejects this, try "openai/gpt-4.1"
MAX_CHARS = 8_000          # cap content sent to the LLM (cost/latency guard)

_aiml = OpenAI(
    base_url="https://api.aimlapi.com/v1",
    api_key=os.environ["OPENAI_API_KEY"],
)


def fetch_page(url: str) -> str | None:
    """Fetch a search-results page through Bright Data Web Unlocker."""
    username = os.environ["BRIGHTDATA_USERNAME"]
    password = os.environ["BRIGHTDATA_PASSWORD"]
    proxy = f"https://{username}:{password}@brd.superproxy.io:33335"
    try:
        resp = requests.get(url, proxies={"http": proxy, "https": proxy}, verify=False, timeout=60)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[scraper] Bright Data fetch failed for {url}: {e}")
        return None


def _reduce(content: str) -> str:
    """Strip a raw HTML page down to visible text, PRESERVING listing links."""
    if _HAS_BS4 and "<html" in content.lower():
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        # Preserve listing URLs: replace <a href> with "text [URL]"
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Only keep links that look like property detail pages
            # Match ONLY individual property pages, not search/listing pages
            is_individual = (
                "/to-rent/details/" in href           # Zoopla individual listing
                or "/properties/" in href              # Rightmove individual listing
                or "/flatshare/flatshare_detail" in href  # SpareRoom individual
            )
            if is_individual:
                if href.startswith("/"):
                    # Add domain back
                    if "zoopla" in content[:5000].lower():
                        href = "https://www.zoopla.co.uk" + href
                    elif "rightmove" in content[:5000].lower():
                        href = "https://www.rightmove.co.uk" + href
                    elif "spareroom" in content[:5000].lower():
                        href = "https://www.spareroom.co.uk" + href
                a.string = f"{a.get_text(strip=True)} [URL: {href}]"
        content = soup.get_text(separator="\n", strip=True)
    return content[:MAX_CHARS]


_SCHEMA_PROMPT = """You are a precise data extractor for UK rental listings.
From the page text below, extract every distinct property listing you can find.
IMPORTANT: Only extract listings whose ADDRESS visibly contains the location/postcode the user is searching for.
Skip listings from other areas even if they appear on the page.
Return ONLY valid JSON, no prose, in this exact shape:

{"listings": [
  {
    "title": string,
    "price_pcm": number | null,        // monthly rent in GBP, digits only
    "bedrooms": number | null,
    "property_type": string | null,    // "flat", "studio", "house", etc.
    "address": string | null,
    "listing_url": string | null,        // FULL URL to the INDIVIDUAL property page (must contain /details/ or /properties/). Look for [URL: https://...] markers next to each listing. NEVER use a search results URL.
    "agent": string | null,
    "available_from": string | null,
    "summary": string | null           // one short line
  }
]}

If a field is unknown, use null. Do not invent listings."""


def extract_listings(page_text: str, max_results: int = 15) -> list[dict]:
    """Use the AIML LLM to turn messy page text into structured listings."""
    resp = _aiml.chat.completions.create(
        model=AIML_MODEL,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {"role": "system", "content": _SCHEMA_PROMPT},
            {"role": "user", "content": page_text},
        ],
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return []
    return data.get("listings", [])[:max_results]


import time as _time
_cache: dict = {}
_CACHE_TTL = 3600  # 10 minutes

def _fetch_and_extract(url: str, max_results: int) -> list[dict]:
    page = fetch_page(url)
    if not page:
        return []
    return extract_listings(_reduce(page), max_results=max_results)


def search_properties(search_url: str, max_results: int = 15) -> list[dict]:
    """End-to-end: portal search URL -> structured listings. Results cached for 10 min."""
    key = (search_url, max_results)
    entry = _cache.get(key)
    if entry and (_time.time() - entry["ts"] < _CACHE_TTL):
        print(f"[scraper] Cache hit")
        return entry["data"]
    result = _fetch_and_extract(search_url, max_results=max_results)
    _cache[key] = {"ts": _time.time(), "data": result}
    return result





def _build_portal_urls(location: str, property_type: str = "property",
                       beds_min=None, price_max=None) -> dict[str, str]:
    """Build search URLs for Zoopla, Rightmove, and SpareRoom."""
    import re as _re_local
    loc = location.strip()
    # Detect UK postcode (e.g. RG1, SW1A, E1, M1)
    postcode_match = _re_local.match(r"^([A-Za-z]{1,2}[0-9][A-Za-z0-9]?)", loc)
    is_postcode = bool(postcode_match) and len(loc) <= 8
    if is_postcode:
        slug = loc.lower().replace(" ", "-")
    else:
        slug = loc.lower().replace(" ", "-").replace(",", "")

    # Zoopla
    zoopla = f"https://www.zoopla.co.uk/to-rent/property/{slug}/"
    z_params = []
    if beds_min: z_params.append(f"beds_min={beds_min}")
    if price_max: z_params.append(f"price_max={price_max}")
    if z_params: zoopla += "?" + "&".join(z_params)

    # Rightmove (uses location identifier - fallback to search by name)
    rightmove = f"https://www.rightmove.co.uk/property-to-rent/{slug}.html"
    r_params = []
    if price_max: r_params.append(f"maxPrice={price_max}")
    if beds_min: r_params.append(f"minBedrooms={beds_min}")
    if r_params: rightmove += "?" + "&".join(r_params)

    # SpareRoom
    spareroom = f"https://www.spareroom.co.uk/flatshare/{slug}/"
    if price_max:
        spareroom += f"?max_rent={price_max}&per=pcm"

    return {"Zoopla": zoopla, "Rightmove": rightmove, "SpareRoom": spareroom}


def search_all_portals_parallel(
    location: str,
    property_type: str = "property",
    beds_min: int = None,
    price_max: int = None,
    max_results: int = 15,
) -> list[dict]:
    """Fetch Zoopla, Rightmove, and SpareRoom in parallel, merge results."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    urls = _build_portal_urls(location, property_type, beds_min, price_max)
    results = []

    def fetch_one(portal: str, url: str):
        print(f"[scraper] Starting {portal}: {url}")
        try:
            listings = search_properties(url, max_results=max_results)
            for l in listings:
                l["source"] = portal
            print(f"[scraper] {portal} returned {len(listings)} listings")
            return listings
        except Exception as e:
            print(f"[scraper] {portal} failed: {e}")
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        # Only Zoopla by default — Rightmove is slow, SpareRoom is blocked
        urls = {"Zoopla": urls["Zoopla"]}
        futures = {ex.submit(fetch_one, p, u): p for p, u in urls.items()}
        for fut in as_completed(futures):
            results.extend(fut.result())

    # Deduplicate by address (case-insensitive)
    seen = set()
    deduped = []
    for r in results:
        addr = (r.get("address") or "").lower().strip()
        if addr and addr in seen:
            continue
        seen.add(addr)
        deduped.append(r)

    return deduped[:max_results]




def stream_portals(
    location: str,
    property_type: str = "property",
    beds_min: int = None,
    price_max: int = None,
    max_results: int = 10,
):
    """Yield results portal-by-portal as soon as each completes."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    urls = _build_portal_urls(location, property_type, beds_min, price_max)

    def fetch_one(portal: str, url: str):
        try:
            listings = search_properties(url, max_results=max_results)
            for l in listings:
                l["source"] = portal
            return portal, listings
        except Exception as e:
            print(f"[scraper] {portal} failed: {e}")
            return portal, []

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(fetch_one, p, u): p for p, u in urls.items()}
        for fut in as_completed(futures):
            portal, listings = fut.result()
            yield portal, listings


if __name__ == "__main__":
    # GO / NO-GO TEST
    # Paste a REAL search URL: run a search on zoopla.co.uk / rightmove.co.uk
    # in your browser and copy the address bar. Placeholder below:
    test_url = "https://www.zoopla.co.uk/to-rent/property/reading/?beds_min=2&price_max=1500"

    listings = search_properties(test_url, max_results=10)
    print(f"Extracted {len(listings)} listings\n")
    for i, lst in enumerate(listings, 1):
        print(f"{i}. {lst.get('title')} — £{lst.get('price_pcm')}/pcm — "
              f"{lst.get('bedrooms')} bed — {lst.get('address')}")