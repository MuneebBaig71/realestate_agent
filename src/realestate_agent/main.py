from agents import Agent,Runner,function_tool,handoff,SQLiteSession,OpenAIChatCompletionsModel,set_tracing_disabled,set_default_openai_api,set_default_openai_client
from agents.tool import WebSearchTool
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
import asyncio
import os
import json
from typing import Optional
from realestate_agent.scraper import search_properties as _scrape_properties
from realestate_agent.scraper import search_all_portals_parallel as _scrape_all

set_tracing_disabled(disabled=True)  # Open AI Tracing == Disable
set_default_openai_api("responses")

BASE_URL = "https://api.aimlapi.com/v1"
MODEL = 'openai/gpt-4o-mini'
api_key = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    api_key=api_key,
    base_url=BASE_URL
)
set_default_openai_client(client)

SESSION_DB = "realestate_agent.db"
_SESSIONS: dict[str, SQLiteSession] = {}

def get_session(sid: str) -> SQLiteSession:
    # reuse per-session-id to avoid opening repeatedly
    s = _SESSIONS.get(sid)
    if s is None:
        s = SQLiteSession(sid, SESSION_DB)
        _SESSIONS[sid] = s
    return s


def _build_zoopla_url(
    location: str,
    property_type: str = "property",
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    price_max: Optional[int] = None,
    price_min: Optional[int] = None,
) -> str:
    """Build a Zoopla search URL using the slug format that Bright Data can access."""
    slug = location.lower().strip().replace(" ", "-").replace(",", "")
    ptype = "property"  # Zoopla doesn't have a /rooms/ path, just /property/
    url = f"https://www.zoopla.co.uk/to-rent/{ptype}/{slug}/"
    params = []
    if beds_min is not None:
        params.append(f"beds_min={beds_min}")
    if beds_max is not None:
        params.append(f"beds_max={beds_max}")
    if price_max is not None:
        params.append(f"price_max={price_max}")
    if price_min is not None:
        params.append(f"price_min={price_min}")
    if params:
        url += "?" + "&".join(params)
    return url


def _market_badge(price_pcm: Optional[float], all_prices: list[float]) -> str:
    """Return a price-vs-market badge string."""
    if price_pcm is None or len(all_prices) < 2:
        return ""
    median = sorted(all_prices)[len(all_prices) // 2]
    if price_pcm < median * 0.93:
        return "🟢 Below market"
    elif price_pcm > median * 1.07:
        return "🔴 Above market"
    else:
        return "🟡 Around market"


@function_tool()
def find_properties(
    location: str,
    property_type: str = "property",
    beds_min: int = None,
    beds_max: int = None,
    price_max: int = None,
    price_min: int = None,
    max_results: int = 10,
    near: str = None,
) -> str:
    """
    Search for rental properties in the UK using live Zoopla data via Bright Data.
    Returns structured listings with price-vs-market badges.

    Args:
        location: City or area NAME ONLY (e.g. "Reading", "Manchester", "Camden"). Do NOT use postcodes like "RG1" — convert to the area name first.
        property_type: "property", "flat", "house", "room", "studio"
        beds_min: Minimum number of bedrooms
        beds_max: Maximum number of bedrooms
        price_max: Maximum monthly rent in GBP
        price_min: Minimum monthly rent in GBP
        max_results: Number of listings to return (default 10)
        near: OPTIONAL reference point (e.g. "Royal Berkshire Hospital", "Reading Station"). If provided, each listing gets walking + driving distance automatically appended.
    """
    print(f"[agent] find_properties called with: location={location!r}, property_type={property_type!r}, beds_min={beds_min}, price_max={price_max}, near={near!r}")
    listings = _scrape_all(
        location=location,
        property_type=property_type,
        beds_min=beds_min,
        price_max=price_max,
        max_results=max_results,
    )
    if not listings:
        return f"No listings found for '{location}'. Try a different location or adjust filters."

    # compute market badges
    prices = [l["price_pcm"] for l in listings if l.get("price_pcm")]
    header = f"Live listings for '{location}' via Bright Data ({len(listings)} found)"
    if near:
        header += f" — with distance to {near}"
    lines = [header + ":\n"]

    # Helper: inline distance computation using POSTCODE (more reliable than full address)
    import re as _re_dist
    def _extract_postcode(addr):
        """Extract UK postcode area or full postcode from messy address."""
        if not addr: return None
        # Try full postcode: RG1 5AN, SW1A 1AA, etc.
        m = _re_dist.search(r"\b([A-Z]{1,2}[0-9][A-Z0-9]?\s+[0-9][A-Z]{2})\b", addr.upper())
        if m: return m.group(1)
        # Fall back to area only: RG1, SW1A, M1
        m = _re_dist.search(r"\b([A-Z]{1,2}[0-9][A-Z0-9]?)\b", addr.upper())
        if m: return m.group(1)
        return None

    def _compute_distance(addr, ref):
        import requests as _req
        try:
            def geo(q):
                r = _req.get("https://nominatim.openstreetmap.org/search",
                            params={"q": q + ", UK", "format": "json", "limit": 1},
                            headers={"User-Agent": "realestate-agent/1.0"}, timeout=8)
                d = r.json()
                if not d:
                    print(f"[distance] ❌ Nominatim nothing for: {q}")
                    return None
                print(f"[distance] ✅ Geocoded '{q}' → {d[0]['lat']},{d[0]['lon']}")
                return (float(d[0]["lat"]), float(d[0]["lon"]))

            # Prefer postcode for the listing — far more reliable than street address
            postcode = _extract_postcode(addr)
            listing_query = postcode if postcode else addr
            print(f"[distance] Using '{listing_query}' (extracted from '{addr}')")
            a, b = geo(listing_query), geo(ref)
            if not a or not b: return None
            def rt(profile):
                u = f"https://router.project-osrm.org/route/v1/{profile}/{a[1]},{a[0]};{b[1]},{b[0]}"
                r = _req.get(u, params={"overview": "false"}, timeout=10)
                d = r.json()
                if d.get("code") != "Ok":
                    print(f"[distance] ❌ OSRM {profile} failed: {d.get('code')}")
                    return None
                km = d["routes"][0]["distance"]/1000
                mins = int(d["routes"][0]["duration"]/60)
                print(f"[distance] ✅ {profile}: {km:.1f}km, {mins}min")
                return (km, mins)
            return {"walk": rt("foot"), "drive": rt("driving") or rt("car")}
        except Exception as e:
            print(f"[distance] 💥 {addr} -> {ref} crashed: {e}")
            return None

    for i, l in enumerate(listings, 1):
        badge = _market_badge(l.get("price_pcm"), prices)
        dist_line = ""
        if near and l.get("address"):
            # If `near` doesn't include the city, prepend it (e.g. "Town Centre" -> "Reading Town Centre")
            qualified_ref = near if location.lower() in near.lower() else f"{location} {near}"
            print(f"[distance] computing for: {l['address']} -> {qualified_ref}")
            d = _compute_distance(l["address"], qualified_ref)
            if d:
                if d.get("walk"):
                    dist_line += f"   🚶 Walking: {d['walk'][0]:.1f} km — about {d['walk'][1]} min\n"
                # Only show driving if meaningfully different from walking
                if d.get("drive") and (not d.get("walk") or abs(d['drive'][1] - d['walk'][1]) > 3):
                    dist_line += f"   🚗 Driving: {d['drive'][0]:.1f} km — about {d['drive'][1]} min\n"
        lines.append(
            f"{i}. {l.get('title') or l.get('address', 'N/A')}\n"
            f"   💰 £{l.get('price_pcm', '?')}/pcm {badge}\n"
            f"   🛏 {l.get('bedrooms', '?')} bed | {l.get('property_type') or property_type}\n"
            f"   📍 {l.get('address', 'N/A')}\n"
            + dist_line +
            f"   🔗 {l.get('listing_url') or ''}\n"
            f"   🏢 Agent: {l.get('agent') or 'N/A'}\n"
        )
    return "\n".join(lines)



@function_tool()
def get_market_stats(location: str) -> str:
    """
    Get LIVE rental market statistics for a UK location by scraping current listings.
    Use this when the user asks about market conditions, average rents, price trends, or what to expect.
    Returns real aggregated data, not generic estimates.
    """
    print(f"[agent] Computing live market stats for: {location}")
    # Scrape a broad sample (no filters) to get a representative cross-section
    listings = _scrape_all(
        location=location,
        property_type="property",
        beds_min=None,
        price_max=None,
        max_results=30,
    )
    if not listings:
        return f"Could not fetch live data for '{location}'. Try a different city or postcode."

    # Aggregate by bedrooms
    from statistics import median
    by_beds = {}
    all_prices = []
    sources = {}
    for l in listings:
        price = l.get("price_pcm")
        beds = l.get("bedrooms")
        src_portal = l.get("source") or "Unknown"
        if not price:
            continue
        all_prices.append(price)
        sources[src_portal] = sources.get(src_portal, 0) + 1
        if beds is not None:
            by_beds.setdefault(beds, []).append(price)

    if not all_prices:
        return f"Could not extract pricing data for '{location}'."

    overall_median = int(median(all_prices))
    price_min = int(min(all_prices))
    price_max = int(max(all_prices))
    below_median = sum(1 for p in all_prices if p < overall_median)

    lines = [
        f"📊 **Live Rental Market — {location}**",
        f"_Sampled from {len(listings)} active listings across {', '.join(sources.keys())} just now_\n",
        f"**Overall median rent:** £{overall_median}/pcm",
        f"**Price range:** £{price_min} – £{price_max}/pcm",
        f"**Good-deal pool:** {below_median} of {len(all_prices)} listings priced below median\n",
        f"**By bedroom count:**",
    ]
    for beds in sorted(by_beds.keys()):
        if beds is None:
            continue
        prices = by_beds[beds]
        if len(prices) >= 2:
            lines.append(f"  • {beds}-bed: median £{int(median(prices))}/pcm "
                         f"(range £{int(min(prices))}–£{int(max(prices))}, {len(prices)} listings)")

    lines.append(f"\n**Source breakdown:**")
    for portal, count in sources.items():
        lines.append(f"  • {portal}: {count} listings")

    lines.append(f"\n_Source: live scrape via Bright Data — Zoopla, Rightmove, SpareRoom_")
    return "\n".join(lines)



@function_tool()
def get_distance(listing_address: str, reference_point: str) -> str:
    """
    Calculate walking and driving distance/time between a property and a reference point.
    Use this when the user asks how far a listing is from a hospital, train station, university,
    or any named location. Uses OpenStreetMap (free, no API key).

    Args:
        listing_address: Full address of the property (e.g. "Bath Road, Reading RG30")
        reference_point: Reference location (e.g. "Royal Berkshire Hospital, Reading" or "Reading Station")
    """
    import requests as _req
    print(f"[distance] {listing_address} -> {reference_point}")

    def geocode(query: str):
        try:
            resp = _req.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query + ", UK", "format": "json", "limit": 1},
                headers={"User-Agent": "realestate-agent-hackathon/1.0"},
                timeout=10,
            )
            data = resp.json()
            if not data:
                return None
            return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            print(f"[distance] geocode failed for '{query}': {e}")
            return None

    a = geocode(listing_address)
    b = geocode(reference_point)
    if not a or not b:
        return f"Could not locate one of the addresses on the map. Tried: '{listing_address}' and '{reference_point}'."

    def route(profile: str):
        try:
            url = f"https://router.project-osrm.org/route/v1/{profile}/{a[1]},{a[0]};{b[1]},{b[0]}"
            resp = _req.get(url, params={"overview": "false"}, timeout=15)
            data = resp.json()
            if data.get("code") != "Ok":
                return None
            r = data["routes"][0]
            return {"km": r["distance"] / 1000, "mins": int(r["duration"] / 60)}
        except Exception as e:
            print(f"[distance] {profile} routing failed: {e}")
            return None

    walking = route("foot")
    driving = route("driving") or route("car")

    lines = [f"📍 **From** {listing_address}\n   **To** {reference_point}\n"]
    if walking:
        lines.append(f"   🚶 Walking: {walking['km']:.1f} km — about {walking['mins']} min")
    if driving:
        lines.append(f"   🚗 Driving: {driving['km']:.1f} km — about {driving['mins']} min")
    if not walking and not driving:
        lines.append("   _Routing service unavailable._")
    return "\n".join(lines)


class Query_Output(BaseModel):
    price: str
    location: str
    postcode: str
    link: str
    property_type: str

def is_email_query(query: str) -> bool:
    keywords = [
        "email", "contact", "reach out", "inquire", "inquiry", "message", "send an email"
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)

def is_location_query(query: str) -> bool:
    keywords = [
        "distance", "how far", "nearest", "close to", "near", "from", "location", "coordinates"
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)

@function_tool()
def user_output(info:Query_Output) :
    """
    This is a function tool that formats the output of the real estate agent query.
    """
    return f"Following is the property found matching your search, Price: {info.price}, Location: {info.location}, Postcode: {info.postcode}, Link: {info.link}, Property Type: {info.property_type}"
    

email_agent = Agent(
    name="Email Assistant",
    instructions="""You are an email agent assistant. When handed off a query, always write a complete, polite, and professional email based on the user's request.

FORMATTING RULES (very important):
- Start with "**Subject:** Your subject here" using double asterisks for bold
- Use a clear greeting like "Dear [Landlord/Agent's Name],"
- Use **double asterisks** for any bold text, never single asterisks
- Use square brackets for placeholders the user needs to fill: [Your Name], [Date], etc.
- End with "Kind regards," then the placeholder lines on separate lines

You can assist with composing emails to landlords, agents, or other relevant parties based on user input. You also have memory capabilities!""",
    tools=[],
    model=MODEL
)



room_agent = Agent(
    name="Room Assistant",
    instructions="""You are a room agent assistant. You help users find rooms to rent in the UK.
    Use the find_properties tool with property_type='room' to fetch live listings from Zoopla via Bright Data.
    Always extract location, budget (price_max), and beds from the user query before calling the tool. If the user gives a postcode like 'RG1' or 'E1', convert it to the area name (RG1 → Reading, E1 → London) before passing to find_properties.
    Present results clearly with the price-vs-market badge included.
    You also have memory capabilities!""",
    tools=[find_properties],
    model=MODEL
)

flat_agent = Agent(
    name="Flat Assistant",
    instructions="""You are a flat agent assistant. You help users find flats to rent in the UK.
    Use the find_properties tool with property_type='flat' to fetch live listings from Zoopla via Bright Data.
    Always extract location, budget (price_max), and beds from the user query before calling the tool. If the user gives a postcode like 'RG1' or 'E1', convert it to the area name (RG1 → Reading, E1 → London) before passing to find_properties.
    Present results clearly with the price-vs-market badge included.
    You also have memory capabilities!""",
    tools=[find_properties],
    model=MODEL
)

studio_agent = Agent(
    name="Studio Assistant",
    instructions="""You are a studio/property agent assistant. You help users find studios or general properties to rent in the UK.
    Use the find_properties tool to fetch live listings from Zoopla via Bright Data.
    Always extract location, budget (price_max), and beds from the user query before calling the tool. If the user gives a postcode like 'RG1' or 'E1', convert it to the area name (RG1 → Reading, E1 → London) before passing to find_properties.
    Present results clearly with the price-vs-market badge included.
    You also have memory capabilities!""",
    tools=[find_properties],
    model=MODEL
)

location_agent = Agent(
    name="Location Assistant",
    instructions="""You are a location agent assistant. You find UK properties near specific landmarks (hospitals, train stations, universities, workplaces).

CRITICAL RULE: When the user mentions a landmark (hospital, station, university, etc.):
- Call find_properties with location=city_name AND near="landmark name"
- The tool will automatically compute walking + driving distances from each listing to the landmark
- Example: user says "rooms near Reading hospital" → call find_properties(location="Reading", property_type="room", near="Royal Berkshire Hospital")

NEVER estimate distances yourself — only use what find_properties returns.

FORMAT each result like:
**1. [Listing title]**
💰 £[price]/pcm — [badge]
📍 [address]
[output from get_distance, showing 🚶 Walking and 🚗 Driving]
🔗 [listing_url]

You have memory capabilities — remember the user's reference point across follow-up questions.""",
    tools=[find_properties, get_distance],
    model=MODEL
)

agent = Agent(
    name="Realestate Assistant",
    instructions="""You are a helpful UK real estate assistant.
    Use the find_properties tool to search for live rental listings via Bright Data (Zoopla, Rightmove, SpareRoom).
    Use the get_market_stats tool whenever the user asks about market conditions, average rents, "what's the market like", price trends, or general market overview. This returns REAL aggregated stats from live scraped data — never give generic answers about the market.
    Extract location, property_type, beds, and budget from the user's query and call find_properties directly.
    Hand off to room_agent for rooms, flat_agent for flats, studio_agent for studios/general properties.
    Hand off to email_agent when the user wants to contact a landlord or agent.
    Always show the price-vs-market badge from the tool results.
    Provide detailed information about properties using the user_output tool.""",
    model=MODEL,
    tools=[find_properties, get_market_stats, get_distance, user_output],
    handoffs=[room_agent, flat_agent, studio_agent, location_agent, email_agent],
)
async def main():
    # choose a session id once (per user) or per message
    session_id = input("Session ID (e.g., user123): ").strip() or "default"
    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Exiting...")
            break
        try:
            session = get_session(session_id)  # <-- per-user session
            if is_location_query(user_input):
                result = await Runner.run(location_agent, input=user_input, session=session)
            else:
                result = await Runner.run(agent, input=user_input, session=session)
            print("Agent:", result.final_output)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())


