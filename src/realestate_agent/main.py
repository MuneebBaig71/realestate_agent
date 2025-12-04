from agents import Agent,Runner,function_tool,handoff,SQLiteSession,OpenAIChatCompletionsModel,set_tracing_disabled,set_default_openai_api,set_default_openai_client
from agents.tool import WebSearchTool
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
import asyncio
import os

set_tracing_disabled(disabled=True)  # Open AI Tracing == Disable
set_default_openai_api("responses")

BASE_URL = "https://api.aimlapi.com/v1"
MODEL =  'openai/gpt-4.1-2025-04-14'
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
    instructions="""You are an email agent assistant. When handed off a query, always write a complete, polite, and professional email based on the user's request. Include a subject line and a greeting. You can assist with composing emails to landlords, agents, or other relevant parties based on user input. You also have memory capabilities!""",
    tools=[WebSearchTool()],
    model=MODEL
)



room_agent = Agent(
    name="Room Assistant",
    instructions="""You are a room agent assistant. You help users find information about rooms in the UK from websites like Rightmove, Zoopla, and SpareRoom. You answer questions related to price, location, postcode, link, and property type, using the web search tool to get live data every time.
    You also have memory capabilities!""",
    tools=[WebSearchTool()],
    model=MODEL
)

flat_agent = Agent(
    name="Flat Assistant",
    instructions="""You are a flat agent assistant. You help users find information about flats in the UK from websites like Rightmove, Zoopla, and SpareRoom. You answer questions related to price, location, postcode, link, and property type, using the web search tool to get live data every time.   
    You also have memory capabilities!""",
    tools=[WebSearchTool()],
    model=MODEL
)

studio_agent = Agent(
    name="Studio Assistant",
    instructions="""You are a real estate agent assistant. You help users find information about properties in the UK from websites like Rightmove, Zoopla, and SpareRoom. You answer questions related to price, location, postcode, link, and property type, using the web search tool to get live data every time.
    Use the room_agent, flat_agent, studio_agent, and house_agent to handle specific queries about rooms, flats, studios, and houses respectively.
    You can also handle general queries about real estate in the UK, such as market trends, property types, and investment advice.
    You also have memory capabilities!""",
    tools=[WebSearchTool()],
    model=MODEL
)

location_agent = Agent(
    name="Location Assistant",
    instructions="""You are a location agent assistant. You help users find information about locations in the UK using the geo_tool to convert location names into coordinates (latitude and longitude). You provide accurate and concise information based on user queries.
    You also have memory capabilities!""",
    tools=[WebSearchTool() ],
    model=MODEL
)

agent = Agent(
    name="Realestate Assistant",
    instructions="You are a helpful assistant for real estate inquiries. You will assist users with searching rooms according to postcode, price, distance from specific location, search website like Rightmove,Zoopla and Spareroom, use the websearch tool to find relevant listings, help them write emails with the help of the email_agent and provide detailed information about properties in the format set by the tool user_output.",
    model=MODEL,
    tools=[WebSearchTool(), user_output],
    handoffs=[room_agent, flat_agent, studio_agent,location_agent, email_agent],
    
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


