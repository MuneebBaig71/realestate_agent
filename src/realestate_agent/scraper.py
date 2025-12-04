"""
Polite Zoopla scraper (Playwright, Python, async)
- Single responsibility: fetch a search results page and extract listing cards.
- Selector-driven via a site profile so you can tweak without code changes.
- Includes throttling, user-agent, basic error handling, optional screenshots.

USAGE (CLI):
    python -m asyncio -c "import asyncio; \
        from zoopla_scraper import scrape_zoopla; \
        print(asyncio.run(scrape_zoopla('Reading RG2', price_max=800, page=1)))"

Or from FastAPI:
    from zoopla_scraper import scrape_zoopla
    results = await scrape_zoopla("Reading RG2", price_max=800, furnished=True)

NOTE:
- Respect robots.txt / TOS. Keep request volume low. Use for demo/prototyping.
- If a CAPTCHA is detected, we stop and return an informative status.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import math
import random
import time

from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError


# ---------------------------- Config & Models ----------------------------

@dataclass
class Listing:
    title: str
    price_gbp: Optional[int]
    address: str
    postcode: Optional[str]
    url: str
    summary: Optional[str]
    features: List[str]
    image: Optional[str]
    source: str = "zoopla"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_PROFILE = {
    # Root selector for each card on SRP (search results page)
    "card": "[data-testid='listing-card'], article, li[role='listitem']",
    # Within each card, how to find content
    "title": "[data-testid='listing-title'], h2, a[aria-label]",
    "price": "[data-testid='listing-price'], [data-testid='price']",
    "address": "[data-testid='listing-description'], [data-testid='address'], address, .css-*",
    "link": "a[href*='/to-rent/'], a[href*='/to-rent/details'], a[href*='/to-rent/property']",
    "summary": "[data-testid='listing-description'], p, .Text__StyledText",
    "features": "[data-testid='listing-features'] li, ul li, .features li",
    "image": "img",
    # Captcha heuristics on Zoopla-like pages
    "captcha": [
        "iframe[src*='recaptcha']",
        "div.g-recaptcha",
        "iframe[src*='hcaptcha']",
        "text=/verify you are human|unusual traffic|complete the challenge/i"
    ],
    # SRP container (optional, improves wait reliability)
    "results_container": "[data-testid='regular-listings'], [data-testid='search-results'], main"
}


def build_search_url(
    location: str,
    price_max: Optional[int] = None,
    price_min: Optional[int] = None,
    furnished: Optional[bool] = None,
    room_in_shared: Optional[bool] = True,
    page: int = 1,
) -> str:
    """
    Construct a Zoopla search URL with conservative, generic params.
    (Zoopla’s real param names can change. Treat this as a starting point.)
    """
    base = "https://www.zoopla.co.uk/to-rent/property/"
    # naive location slug
    slug = location.lower().replace(" ", "-")
    url = f"{base}{slug}/?search_source=to-rent"

    if price_min:
        url += f"&price_min={int(price_min)}"
    if price_max:
        url += f"&price_max={int(price_max)}"

    # crude filters; safe to omit if they don't work
    if furnished is True:
        url += "&furnished_state=furnished"
    elif furnished is False:
        url += "&furnished_state=unfurnished"

    if room_in_shared:
        url += "&property_type=house-share"

    if page and page > 1:
        url += f"&pn={int(page)}"

    return url


# ---------------------------- Scraper Core ----------------------------

async def _looks_like_captcha(page, selectors: List[str]) -> bool:
    try:
        for sel in selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                return True
        return False
    except Exception:
        return False


async def _polite_delay(min_ms=400, max_ms=900):
    await asyncio.sleep(random.uniform(min_ms/1000.0, max_ms/1000.0))


async def _get_text(el, selector: str) -> Optional[str]:
    try:
        loc = el.locator(selector).first
        if await loc.count() == 0:
            return None
        txt = (await loc.inner_text()).strip()
        return " ".join(txt.split())
    except Exception:
        return None


async def _get_attr(el, selector: str, attr: str) -> Optional[str]:
    try:
        loc = el.locator(selector).first
        if await loc.count() == 0:
            return None
        return await loc.get_attribute(attr)
    except Exception:
        return None


def _parse_price_gbp(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    # accept "£795 pcm" / "£180 pw" etc. We’ll only return the numeric part (per month guess)
    import re
    m = re.search(r"£\s*([\d,]+)", text)
    if not m:
        return None
    n = int(m.group(1).replace(",", ""))
    return n


def _extract_postcode(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    import re
    # Simple UK postcode regex (loose)
    pc = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s?(\d[A-Z]{2})\b", address, flags=re.I)
    return pc.group(0).upper() if pc else None


async def parse_search_results(page, profile: Dict[str, str]) -> List[Listing]:
    cards = page.locator(profile["card"])
    count = await cards.count()
    listings: List[Listing] = []

    for i in range(count):
        el = cards.nth(i)
        title = await _get_text(el, profile["title"]) or ""
        price_txt = await _get_text(el, profile["price"])
        address = await _get_text(el, profile["address"]) or ""
        url = await _get_attr(el, profile["link"], "href") or ""
        if url and url.startswith("/"):
            # normalize relative URLs
            url = "https://www.zoopla.co.uk" + url
        summary = await _get_text(el, profile["summary"])
        image = await _get_attr(el, profile["image"], "src")

        features = []
        try:
            feats = el.locator(profile["features"])
            fcount = await feats.count()
            for j in range(min(fcount, 8)):
                tx = (await feats.nth(j).inner_text()).strip()
                if tx:
                    features.append(" ".join(tx.split()))
        except Exception:
            pass

        listings.append(
            Listing(
                title=title,
                price_gbp=_parse_price_gbp(price_txt),
                address=address,
                postcode=_extract_postcode(address),
                url=url,
                summary=summary,
                features=features,
                image=image,
            )
        )

    return listings


# ---------------------------- Public API ----------------------------

import asyncio  # after top-level annotations

async def scrape_zoopla(
    location: str,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    furnished: Optional[bool] = None,
    room_in_shared: Optional[bool] = True,
    page: int = 1,
    selector_profile_path: Optional[str] = None,
    headless: bool = True,
    take_screenshot: bool = False,
    timeout_ms: int = 30000,
) -> Dict[str, Any]:
    """
    Fetch a Zoopla search results page and return parsed listings.

    Returns:
        {
          "status": "ok"|"captcha"|"error",
          "url": "...",
          "count": N,
          "listings": [ {title, price_gbp, address, postcode, url, ...}, ... ],
          "note": optional string,
          "screenshot": optional file path,
        }
    """
    profile = DEFAULT_PROFILE.copy()
    if selector_profile_path and Path(selector_profile_path).exists():
        try:
            override = json.loads(Path(selector_profile_path).read_text())
            profile.update(override or {})
        except Exception:
            pass

    url = build_search_url(
        location=location,
        price_min=price_min,
        price_max=price_max,
        furnished=furnished,
        room_in_shared=room_in_shared,
        page=page,
    )

    screenshot_path = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        page_obj = await context.new_page()

        try:
            await page_obj.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Optional: wait for results container to stabilize
            try:
                if profile.get("results_container"):
                    await page_obj.wait_for_selector(profile["results_container"], timeout=8000)
            except PWTimeoutError:
                pass

            # Captcha guardrail (no bypassing — just exit cleanly)
            if await _looks_like_captcha(page_obj, profile.get("captcha", [])):
                if take_screenshot:
                    screenshot_path = f"zoopla_captcha_{int(time.time())}.png"
                    await page_obj.screenshot(path=screenshot_path, full_page=True)
                await context.close()
                await browser.close()
                return {"status": "captcha", "url": url, "count": 0, "listings": [], "screenshot": screenshot_path}

            await _polite_delay()

            listings = await parse_search_results(page_obj, profile)

            if take_screenshot:
                screenshot_path = f"zoopla_srp_{int(time.time())}.png"
                await page_obj.screenshot(path=screenshot_path, full_page=True)

            await context.close()
            await browser.close()
            return {
                "status": "ok",
                "url": url,
                "count": len(listings),
                "listings": [x.to_dict() for x in listings],
                "screenshot": screenshot_path,
            }

        except Exception as e:
            try:
                if take_screenshot:
                    screenshot_path = f"zoopla_error_{int(time.time())}.png"
                    await page_obj.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                pass
            await context.close()
            await browser.close()
            return {"status": "error", "url": url, "count": 0, "listings": [], "note": str(e), "screenshot": screenshot_path}
# --- add at bottom of zoopla_scraper.py ---
if __name__ == "__main__":
    import asyncio, json
    out = asyncio.run(scrape_zoopla(
        location="Reading RG2",
        price_max=800,
        furnished=True,
        room_in_shared=True,
        page=1,
        headless=True,           # set False to watch it drive the browser
        take_screenshot=True
    ))
    print(json.dumps(out, indent=2))
