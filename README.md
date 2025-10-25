# Real Estate Agent

A Python-based AI-powered real estate assistant that helps users find properties, compose emails, and get location information. The system uses multiple specialized agents to handle different types of queries and provides a FastAPI web interface.

## 🏠 Features

- **Multi-Agent System**: Specialized agents for different types of queries:
  - **Real Estate Agent**: General property search and information
  - **Email Agent**: Composes professional emails to landlords/agents
  - **Location Agent**: Provides distance and location-based information
  - **Room Agent**: Specialized for room searches on UK platforms
  - **Flat Agent**: Specialized for flat/apartment searches

- **Web Scraping**: Polite Zoopla scraper using Playwright for real-time property data
- **Session Management**: SQLite-based session storage for conversation memory
- **FastAPI Integration**: RESTful API for easy integration
- **AI-Powered**: Uses OpenAI GPT models via AIML API

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/MuneebBaig71/realestate_agent.git
cd realestate_agent
```

2. Install dependencies using uv (recommended):
```bash
uv sync
```

3. Set up environment variables:
```bash
cp .env.example .env
# Add your OPENAI_API_KEY to the .env file
```

### Running the Application

Start the FastAPI server:
```bash
uvicorn realestate_agent.api:app --reload
```

The API will be available at `http://localhost:8000`

## 📡 API Usage

### Endpoint: `/realestate-agent`

Send a POST request with the following structure:

```json
{
  "query": {
    "prompt": "Find me a 2-bedroom flat in London under £2000"
  },
  "session_input": {
    "session_id": "unique_session_id"
  }
}
```

### Example Queries

- **Property Search**: "Find me a room in Reading under £800"
- **Email Composition**: "Write an email to inquire about the property"
- **Location Information**: "How far is this property from the city center?"

## 🏗️ Architecture

### Agent System

The application uses a multi-agent architecture where different agents handle specific types of queries:

```python
# Query routing logic
if is_email_query(prompt):
    result = await Runner.run(email_agent, input=prompt, session=session)
elif is_location_query(prompt):
    result = await Runner.run(location_agent, input=prompt, session=session)
else:
    result = await Runner.run(agent, input=prompt, session=session)
```

### Components

- **`api.py`**: FastAPI application with session management
- **`main.py`**: Agent definitions and query routing logic
- **`scraper.py`**: Zoopla web scraper using Playwright
- **`__init__.py`**: Package initialization

### Data Models

```python
class Query_Output(BaseModel):
    price: str
    location: str
    postcode: str
    link: str
    property_type: str
```

## 🔧 Configuration

### Environment Variables

```bash
OPENAI_API_KEY=your_api_key_here
```

### Scraper Configuration

The Zoopla scraper includes:
- Polite scraping with throttling
- User-agent rotation
- CAPTCHA detection
- Error handling
- Optional screenshots

## 🛠️ Development

### Project Structure

```
realestate_agent/
├── src/
│   └── realestate_agent/
│       ├── __init__.py
│       ├── api.py          # FastAPI application
│       ├── main.py         # Agent definitions
│       └── scraper.py      # Web scraping logic
├── pyproject.toml          # Project configuration
├── uv.lock                # Dependency lock file
└── README.md
```

### Dependencies

- **FastAPI**: Web framework
- **OpenAI Agents**: AI agent framework
- **Playwright**: Web scraping
- **Mem0**: Memory management
- **Pydantic**: Data validation

## 📝 Usage Examples

### Property Search
```bash
curl -X POST "http://localhost:8000/realestate-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"prompt": "Find a studio apartment in Manchester under £1200"},
    "session_input": {"session_id": "user123"}
  }'
```

### Email Composition
```bash
curl -X POST "http://localhost:8000/realestate-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"prompt": "Write an email to inquire about viewing the property"},
    "session_input": {"session_id": "user123"}
  }'
```

## ⚠️ Important Notes

- **Respect Terms of Service**: The scraper is designed for demo/prototyping purposes
- **Rate Limiting**: Built-in throttling to be respectful to scraped websites
- **Session Management**: Each user gets their own SQLite session for conversation memory

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👤 Author

**Muneeb Baig**
- Email: muneebbaig71@gmail.com
- GitHub: [@MuneebBaig71](https://github.com/MuneebBaig71)

## 🔗 Links

- [Repository](https://github.com/MuneebBaig71/realestate_agent)
- [Issues](https://github.com/MuneebBaig71/realestate_agent/issues)