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
