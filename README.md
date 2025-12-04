# 🏠 AI-Powered Real Estate Agent Chatbot

An intelligent chatbot application that helps users search for properties across UK platforms (Rightmove, Zoopla, SpareRoom), get location information, and generate professional inquiry emails using AI-powered agents.

## ✨ Features

- **🔍 Property Search**: Real-time property listings from Rightmove, Zoopla, and SpareRoom
- **📍 Location Intelligence**: Distance calculations, coordinates, and neighborhood information
- **✉️ Email Writer**: AI-generated professional inquiry emails for landlords and agents
- **💬 General Chat**: Multi-purpose real estate assistance
- **🧠 Conversation Memory**: Session-based context retention across conversations
- **🎨 Modern UI**: Animated gradient interface with intuitive chat design

## 🏗️ Architecture

### Multi-Agent System

- **General Chat Agent**: Orchestrates general real estate inquiries
- **Property Search Agent**: Specialized in finding rooms, flats, and studios
- **Location Agent**: Handles geographic queries and distance calculations
- **Email Agent**: Generates professional correspondence

### Tech Stack

- **Frontend**: React 18.2.0 with CSS3 animations
- **Backend**: FastAPI with Python
- **AI Model**: GPT-4.1 (via AIML API)
- **Database**: SQLite for session persistence
- **Tools**: Web search integration for live property data

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 16+
- OpenAI API key (AIML API compatible)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/MuneebBaig71/realestate_agent.git
cd realestate_agent
```

2. **Set up environment variables**
   Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_api_key_here
```

3. **Install Python dependencies**

```bash
pip install -r requirements.txt
# or if using uv
uv sync
```

4. **Install frontend dependencies**

```bash
cd frontend
npm install
```

### Running the Application

1. **Start the Backend**

```bash
# From the root directory
uvicorn src.realestate_agent.api:app --reload
```

The API will be available at `http://localhost:8000`

2. **Start the Frontend**

```bash
# In a new terminal
cd frontend
npm start
```

The React app will open at `http://localhost:3000`

## 💡 Usage

### Property Search

```
"Find a 2-bedroom flat in London under £1500"
"Show me rooms near Manchester University"
"Search for studios in Birmingham with parking"
```

### Location Queries

```
"How far is Reading from London?"
"What's the postcode for Oxford city center?"
"Distance from Royal Berkshire Hospital to Reading"
```

### Email Generation

```
"Write an email to inquire about the flat on Rightmove"
"Draft a message asking about viewing availability"
"Compose an email to the landlord about the room"
```

## 📁 Project Structure

```
realestate_agent/
├── src/
│   └── realestate_agent/
│       ├── main.py          # Agent definitions and CLI
│       ├── api.py           # FastAPI endpoints
│       └── scraper.py       # Web scraping utilities
├── frontend/
│   ├── src/
│   │   ├── App.js           # Main React component
│   │   ├── App.css          # Styling with animations
│   │   └── index.js         # Entry point
│   └── package.json
├── pyproject.toml           # Python dependencies
├── .env                     # Environment variables
└── README.md
```

## 🎯 Use Cases

1. **Students**: Finding affordable accommodation near universities
2. **Professionals**: Quick property search during relocation
3. **Families**: Searching for family-sized properties in specific areas
4. **Property Seekers**: 24/7 intelligent real estate assistance
5. **Real Estate Agents**: Automating initial client inquiries

## 🔮 Future Enhancements

- **Playwright MCP Integration**: Full browser automation for form filling and booking requests
- **Property Comparison Dashboard**: Side-by-side analysis with interactive charts
- **Price Alerts**: Track and notify on price drops for saved properties
- **Tenant Review System**: Community ratings for landlords and properties
- **Smart Commute Calculator**: Travel time analysis to work/university
- **Voice Interface**: Speech-to-text property search
- **Mobile App**: Native iOS and Android applications

## 🛠️ API Endpoints

### `/realestate-agent` (POST)

Search for properties and get AI assistance

**Request Body:**

```json
{
  "query": "Find a flat in London",
  "session_id": "user123"
}
```

**Response:**

```json
{
  "response": "AI-generated response with property listings"
}
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 👥 Authors

- **MuneebBaig71** - [GitHub Profile](https://github.com/MuneebBaig71)


## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for the Real Estate Community**
