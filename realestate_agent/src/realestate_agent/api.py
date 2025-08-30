# api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
from realestate_agent.main import agent, Runner, SQLiteSession,is_email_query, is_location_query, location_agent,email_agent

app = FastAPI()

# --------- Request schema (nested) ---------
class Query(BaseModel):
    prompt: str

class SessionInput(BaseModel):
    session_id: str

class RealEstateRequest(BaseModel):
    query: Query
    session_input: SessionInput

# --------- Per-user sessions (one DB file) ---------
SESSION_DB = "realestate_agent.db"
_SESSIONS: Dict[str, SQLiteSession] = {}

def get_session(sid: str) -> SQLiteSession:
    sess = _SESSIONS.get(sid)
    if sess is None:
        sess = SQLiteSession(sid, SESSION_DB)
        _SESSIONS[sid] = sess
    return sess

def _to_dict(x):
    if hasattr(x, "model_dump"):
        return x.model_dump()
    if hasattr(x, "dict"):
        return x.dict()
    return x

# --------- Route ---------
@app.post("/realestate-agent")
async def realestate_agent(req: RealEstateRequest):
    prompt = req.query.prompt
    session_id = req.session_input.session_id
    session = get_session(session_id)

    if is_email_query(prompt):
        result = await Runner.run(email_agent, input=prompt, session=session)
        print("Email Agent called")
    elif is_location_query(prompt):
        result = await Runner.run(location_agent, input=prompt, session=session)
        print("Location Agent called")
    else:
        result = await Runner.run(agent, input=prompt, session=session)
        print("Realestate Agent called")

    return {"result": _to_dict(getattr(result, "final_output", None))}
