# Real Estate Agent Frontend

A React-based frontend for the Real Estate Agent application.

## Setup Instructions

### Prerequisites

- Node.js (v14+)
- npm or yarn

### Installation

1. Navigate to the frontend directory:

```bash
cd c:\Users\Muneeb\OneDrive\Desktop\Hackathon\realestate_agent\frontend
```

2. Install dependencies:

```bash
npm install
```

This may take several minutes on first install.

### Running the Application

1. Make sure your FastAPI backend is running:

```bash
cd c:\Users\Muneeb\OneDrive\Desktop\Hackathon\realestate_agent
uvicorn src.realestate_agent.api:app --reload
```

2. In a new terminal, start the React development server:

```bash
cd c:\Users\Muneeb\OneDrive\Desktop\Hackathon\realestate_agent\frontend
npm start
```

The app will automatically open at `http://localhost:3000`

### Features

- **Property Search**: Search for properties based on your criteria
- **Location Estimation**: Get information about specific locations
- **Email Writer**: Generate professional emails for property inquiries
- **Session Management**: Maintain conversation history with unique session IDs

### API Configuration

The frontend connects to the backend API at `http://127.0.0.1:8000/realestate-agent`

Make sure your FastAPI server has CORS enabled (it should by default with the updated code).

### Building for Production

```bash
npm run build
```

This creates an optimized production build in the `build` directory.

### Troubleshooting

**"npm: command not found"**

- Make sure Node.js is installed: https://nodejs.org/
- Restart your terminal after installing Node.js

**"API Error"**

- Ensure FastAPI backend is running on port 8000
- Check that CORS middleware is enabled in your FastAPI app
- Open browser DevTools (F12) to see detailed error messages

**Port 3000 already in use**

- Kill the process: `npx kill-port 3000`
- Or specify a different port: `PORT=3001 npm start`
