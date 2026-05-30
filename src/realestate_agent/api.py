import os
# api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from realestate_agent.main import agent, Runner, SQLiteSession, is_email_query, is_location_query, location_agent, email_agent

app = FastAPI()

# --------- Add CORS Middleware ---------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (or specify ["http://127.0.0.1:8001"] for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Request schema ---------
class Query(BaseModel):
    prompt: str

class SessionInput(BaseModel):
    session_id: str

class RealEstateRequest(BaseModel):
    query: Query
    session_input: SessionInput

# --------- Per-user sessions ---------
SESSION_DB = "realestate_agent.db"
_SESSIONS: Dict[str, SQLiteSession] = {}

def get_session(sid: str) -> SQLiteSession:
    """Get or create a session for a user."""
    sess = _SESSIONS.get(sid)
    if sess is None:
        sess = SQLiteSession(sid, SESSION_DB)
        _SESSIONS[sid] = sess
    return sess

def _to_dict(x):
    """Convert object to dictionary."""
    if hasattr(x, "model_dump"):
        return x.model_dump()
    if hasattr(x, "dict"):
        return x.dict()
    return x

# --------- API Endpoint ---------
@app.post("/realestate-agent")
async def realestate_agent_endpoint(req: RealEstateRequest):
    """Main API endpoint for real estate queries."""
    prompt = req.query.prompt.strip()
    session_id = req.session_input.session_id.strip()

    # Detect landmark mentions and inject explicit instruction to use `near` param
    import re as _re2
    landmark_patterns = [
        (r"\bnear\s+(?:the\s+)?([A-Za-z][\w\s&]+?(?:hospital|station|university|college|airport|park|stadium|centre|center))\b", 1),
        (r"\bclose to\s+(?:the\s+)?([A-Za-z][\w\s&]+?(?:hospital|station|university|college|airport|park|stadium|centre|center))\b", 1),
    ]
    for pat, grp in landmark_patterns:
        m = _re2.search(pat, prompt, _re2.IGNORECASE)
        if m:
            landmark = m.group(grp).strip().title()
            prompt = f"{prompt}\n\n[SYSTEM INSTRUCTION: The user mentioned the landmark '{landmark}'. When calling find_properties, you MUST pass near='{landmark}' so real walking and driving distances are computed via OpenStreetMap. Then in your response, copy the 🚶 Walking and 🚗 Driving lines from the tool output VERBATIM for each listing.]"
            print(f"[router] Detected landmark: {landmark}")
            break
    
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")

    session = get_session(session_id)

    try:
        # Route to appropriate agent based on query type
        if is_email_query(prompt):
            result = await Runner.run(email_agent, input=prompt, session=session)
            agent_type = "Email Agent"
        elif is_location_query(prompt):
            result = await Runner.run(location_agent, input=prompt, session=session)
            agent_type = "Location Agent"
        else:
            result = await Runner.run(agent, input=prompt, session=session)
            agent_type = "Realestate Agent"

        return {
            "agent": agent_type,
            "session_id": session_id,
            "result": _to_dict(getattr(result, "final_output", None))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------- Streaming property search ---------
from fastapi.responses import StreamingResponse
import json as _json
import re as _re
from realestate_agent.scraper import stream_portals


def _parse_query(prompt: str) -> dict:
    """Quick regex parse of natural language into structured params."""
    p = prompt.lower()
    # Price
    price_max = None
    # "around 700", "about 700", "~700"
    m = _re.search(r"(?:around|about|approx|approximately|~|circa)\s*£?(\d{3,5})", p)
    if m:
        # add 20% headroom for "around"
        price_max = int(int(m.group(1)) * 1.2)
    else:
        m = _re.search(r"(?:under|below|max|up to|less than|<)\s*£?(\d{3,5})", p)
        if m:
            price_max = int(m.group(1))
        else:
            # bare "£700" or "700pcm" or "700 pcm" or "700 per month"
            m = _re.search(r"£\s*(\d{3,5})|(\d{3,5})\s*(?:pcm|p/m|per month|/month)", p)
            if m:
                price_max = int(m.group(1) or m.group(2))
    # Beds
    beds_min = None
    m = _re.search(r"(\d+)\s*[- ]?bed", p)
    if m: beds_min = int(m.group(1))
    # Property type
    ptype = "property"
    if "room" in p: ptype = "room"
    elif "studio" in p: ptype = "studio"
    elif "flat" in p or "apartment" in p: ptype = "flat"
    elif "house" in p: ptype = "house"
    # Location: try to extract after "in" (supports alphanumeric like "London E1", "RG1")
    location = "Reading"
    m = _re.search(r"\bin\s+([A-Za-z][A-Za-z0-9\s]+?)(?:\s+under|\s+below|\s+for|\s+with|\s+£|\s+at|$|,|\.)", prompt, _re.IGNORECASE)
    if m: location = m.group(1).strip()
    else:
        # fallback: also try "at <location>", "near <location>", or just a capitalized word
        m = _re.search(r"\b(?:at|near)\s+([A-Za-z][A-Za-z0-9\s]+?)(?:\s+under|\s+below|\s+£|$|,)", prompt, _re.IGNORECASE)
        if m: location = m.group(1).strip()
    return {"location": location, "property_type": ptype, "beds_min": beds_min, "price_max": price_max}


def _format_listings(listings: list, portal: str) -> str:
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    if not listings:
        return f"\n### 🌐 {portal} (0 listings found)\nNo matching properties on this portal.\n"
    lines = [f"\n### 🌐 {portal} ({len(listings)} listings)\n📡 Scraped live at {ts} via Bright Data\n"]
    prices = [l["price_pcm"] for l in listings if l.get("price_pcm")]
    median = sorted(prices)[len(prices)//2] if len(prices) >= 2 else None
    for i, l in enumerate(listings, 1):
        badge = ""
        if median and l.get("price_pcm"):
            diff = l["price_pcm"] - median
            pct = abs(diff) / median * 100
            reason = f"£{abs(diff)} {'below' if diff < 0 else 'above'} median of £{median} ({pct:.0f}%, sampled from {len(prices)} listings)"
            if diff < -median * 0.07: badge = f' 🟢 Below market [WHY:{reason}]'
            elif diff > median * 0.07: badge = f' 🔴 Above market [WHY:{reason}]'
            else: badge = f' 🟡 Around market [WHY:{reason}]'
        lines.append(
            f"--LISTING-START--\n"
            f"**{i}. {l.get('title') or l.get('address', 'N/A')}**\n"
            f"💰 £{l.get('price_pcm', '?')}/pcm{badge}\n"
            f"🛏 {l.get('bedrooms', '?')} bed | 📍 {l.get('address', 'N/A')}\n"
            f"🔗 {l.get('listing_url') or 'N/A'}\n"
            f"--LISTING-END--\n"
        )
    return "\n".join(lines)


@app.post("/property-stream")
async def property_stream(req: RealEstateRequest):
    prompt = req.query.prompt.strip()
    params = _parse_query(prompt)

    async def event_gen():
        import asyncio as _asyncio
        from concurrent.futures import ThreadPoolExecutor
        loop = _asyncio.get_event_loop()

        yield f"data: {_json.dumps({'type': 'status', 'message': f'🔍 Searching for {params["property_type"]} in {params["location"]}...'})}\n\n"

        queue = _asyncio.Queue()

        def producer():
            for portal, listings in stream_portals(**params, max_results=10):
                _asyncio.run_coroutine_threadsafe(queue.put((portal, listings)), loop)
            _asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(producer)

        while True:
            item = await queue.get()
            if item is None:
                break
            portal, listings = item
            chunk = _format_listings(listings, portal)
            yield f"data: {_json.dumps({'type': 'partial', 'portal': portal, 'content': chunk, 'count': len(listings)})}\n\n"

        yield f"data: {_json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )


# --------- Speechmatics voice transcription ---------
from fastapi import UploadFile, File
import requests as _req
import time as _t

SPEECHMATICS_API_KEY = os.environ.get("SPEECHMATICS_API_KEY", "")
SPEECHMATICS_URL = "https://asr.api.speechmatics.com/v2/jobs/"


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe uploaded audio via Speechmatics."""
    if not SPEECHMATICS_API_KEY:
        raise HTTPException(500, "SPEECHMATICS_API_KEY not set")

    audio_bytes = await audio.read()
    print(f"[transcribe] Received {len(audio_bytes)} bytes, type: {audio.content_type}")
    if len(audio_bytes) < 1000:
        return {"transcript": "", "error": "Audio too short - hold the mic button and speak"}

    config = {
        "type": "transcription",
        "transcription_config": {"language": "en", "operating_point": "enhanced"}
    }

    files = {
        "data_file": (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm"),
        "config": (None, _json.dumps(config), "application/json"),
    }
    headers = {"Authorization": f"Bearer {SPEECHMATICS_API_KEY}"}
    submit = _req.post(SPEECHMATICS_URL, headers=headers, files=files, timeout=30)
    print(f"[transcribe] Submit status: {submit.status_code}")
    if submit.status_code != 201:
        print(f"[transcribe] Submit error: {submit.text}")
        raise HTTPException(500, f"Speechmatics submit failed: {submit.text}")
    job_id = submit.json()["id"]
    print(f"[transcribe] Job ID: {job_id}")

    # Poll for completion (max 120s)
    final_status = None
    for i in range(120):
        _t.sleep(1)
        status_resp = _req.get(f"{SPEECHMATICS_URL}{job_id}", headers=headers, timeout=10)
        final_status = status_resp.json().get("job", {}).get("status")
        if final_status in ("done", "rejected"):
            print(f"[transcribe] Job finished after {i+1}s with status: {final_status}")
            break

    if final_status != "done":
        raise HTTPException(500, f"Job not done: {final_status}")

    transcript_resp = _req.get(
        f"{SPEECHMATICS_URL}{job_id}/transcript?format=txt",
        headers=headers, timeout=10
    )
    text = transcript_resp.text.strip()
    print(f"[transcribe] Transcript: '{text}' ({len(text)} chars)")
    return {"transcript": text}


@app.post("/speechmatics-jwt")
async def speechmatics_jwt():
    """Issue a temporary JWT for browser WebSocket connection to Speechmatics RT."""
    if not SPEECHMATICS_API_KEY:
        raise HTTPException(500, "SPEECHMATICS_API_KEY not set")
    resp = _req.post(
        "https://mp.speechmatics.com/v1/api_keys?type=rt",
        headers={"Authorization": f"Bearer {SPEECHMATICS_API_KEY}"},
        json={"ttl": 300},
        timeout=10,
    )
    if resp.status_code != 201:
        raise HTTPException(500, f"JWT request failed: {resp.text}")
    return {"jwt": resp.json()["key_value"]}


# --------- Cache pre-warming on startup ---------
from realestate_agent.scraper import stream_portals as _stream

@app.on_event("startup")
async def prewarm_cache():
    """Scrape top UK cities in the background so common demo queries are instant."""
    import threading
    cities = ["Reading", "London", "Manchester", "Birmingham", "Edinburgh", "Bristol", "Leeds", "Cambridge"]
    def warm():
        import time
        time.sleep(5)  # let server boot first
        for city in cities:
            print(f"[prewarm] {city}...")
            try:
                for portal, listings in _stream(location=city, max_results=10):
                    print(f"[prewarm]   {city} / {portal}: {len(listings)} listings cached")
            except Exception as e:
                print(f"[prewarm] {city} failed: {e}")
    threading.Thread(target=warm, daemon=True).start()
    print("[prewarm] Background cache warming started for", len(cities), "cities")
