import React, { useState, useRef, useEffect } from "react";
import "./App.css";

function App() {
  const [sessionId, setSessionId] = useState("default");
  const [loading, setLoading] = useState(false);
  const [activeMenu, setActiveMenu] = useState("chat"); // 'chat', 'property', 'location', 'email'

  // Store messages per menu
  const [menuChats, setMenuChats] = useState({
    chat: [
      {
        id: 1,
        text: "Hello! I'm your Real Estate Agent. I can help you:\n• Search for properties\n• Find location information\n• Write inquiry emails\n\nHow can I assist you today?",
        sender: "bot",
        timestamp: new Date(),
      },
    ],
    property: [
      {
        id: 1,
        text: "🏠 Welcome to Property Search!\n\nI can help you find properties based on:\n• Location (e.g., London, Manchester)\n• Price range\n• Property type (flat, room, studio)\n• Furnishing preferences\n• Other specific requirements\n\nWhat type of property are you looking for?",
        sender: "bot",
        timestamp: new Date(),
      },
    ],
    location: [
      {
        id: 1,
        text: "📍 Location Information Service\n\nI can provide details about:\n• Postcodes and coordinates\n• Neighborhood information\n• Distance from landmarks\n• Local amenities\n• Area characteristics\n\nWhich location would you like to know about?",
        sender: "bot",
        timestamp: new Date(),
      },
    ],
    email: [
      {
        id: 1,
        text: "✉️ Email Writing Assistant\n\nI can help you draft professional emails for:\n• Property inquiries to landlords\n• Questions to real estate agents\n• Booking requests\n• Follow-up messages\n\nWhat email would you like me to help you write?",
        sender: "bot",
        timestamp: new Date(),
      },
    ],
  });

  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  // Get current messages for active menu
  const messages = menuChats[activeMenu];

  const API_URL = "http://127.0.0.1:8000/realestate-agent";

  // Format message text with markdown and links
  const formatMessage = (text) => {
    if (!text) return null;

    // Split by newlines
    const lines = text.split("\n");
    const formatted = [];

    lines.forEach((line, index) => {
      let trimmed = line.trim();

      // HARD RULE: Remove ALL leading asterisks that are NOT part of a bullet list
      // Bullet lists have "* " (asterisk followed by space)
      // Headings have "*Text" (asterisk with no space)
      if (trimmed.startsWith("*") && !trimmed.startsWith("* ")) {
        // This is a heading - remove the asterisk
        trimmed = trimmed.substring(1);
        formatted.push(
          <p
            key={index}
            style={{
              fontWeight: "bold",
              marginTop: "10px",
              marginBottom: "5px",
            }}
          >
            {formatLineContent(trimmed)}
          </p>
        );
        return;
      }

      // Handle bullet points with space after (- item, * item, • item)
      if (trimmed.match(/^[•\-*]\s/)) {
        // Remove bullet and any following whitespace
        const content = trimmed.replace(/^[•\-*]\s+/, "");
        formatted.push(
          <p key={index} style={{ marginLeft: "10px" }}>
            {formatLineContent(content)}
          </p>
        );
        return;
      }

      // Regular text
      if (trimmed) {
        formatted.push(<p key={index}>{formatLineContent(line)}</p>);
      }
      // Empty line
      else {
        formatted.push(<br key={index} />);
      }
    });

    return <div>{formatted}</div>;
  };

  // Format a single line with bold and links
  const formatLineContent = (text) => {
    if (!text) return null;

    // Check if line has bold markdown
    if (text.includes("**")) {
      const parts = text.split("**");
      return (
        <>
          {parts.map((part, i) =>
            i % 2 === 1 ? (
              <strong key={i}>{formatTextWithLinks(part)}</strong>
            ) : (
              formatTextWithLinks(part)
            )
          )}
        </>
      );
    }

    // No bold, just process links
    return formatTextWithLinks(text);
  };

  // Convert URLs to clickable links
  const formatTextWithLinks = (text) => {
    if (!text || typeof text !== "string") return text;

    // First, handle markdown-style links [text](url)
    const markdownLinkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;

    // Replace markdown links with a placeholder that we'll convert later
    let processedText = text;
    const markdownLinks = [];
    let match;

    while ((match = markdownLinkRegex.exec(text)) !== null) {
      markdownLinks.push({ text: match[1], url: match[2] });
    }

    // Replace markdown links with placeholders
    processedText = text.replace(markdownLinkRegex, (match, linkText, url) => {
      return `MDLINK${markdownLinks.findIndex((l) => l.url === url)}MDLINK`;
    });

    // Now handle plain URLs
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = processedText.split(urlRegex);

    return (
      <>
        {parts.map((part, index) => {
          // Check for markdown link placeholder
          const mdLinkMatch = part.match(/MDLINK(\d+)MDLINK/);
          if (mdLinkMatch) {
            const linkIndex = parseInt(mdLinkMatch[1]);
            const link = markdownLinks[linkIndex];
            return (
              <>
                <span key={`space-before-${index}`}> </span>
                <a
                  key={`link-${index}`}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="message-link"
                  title={link.url}
                  style={{
                    cursor: "pointer",
                    color: "#667eea",
                    textDecoration: "none",
                  }}
                >
                  View Listing →
                </a>
              </>
            );
          }

          // Check if this part is a plain URL
          if (part && part.match(/^https?:\/\//)) {
            return (
              <>
                <span key={`space-before-${index}`}> </span>
                <a
                  key={`link-${index}`}
                  href={part}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="message-link"
                  title={part}
                  style={{
                    cursor: "pointer",
                    color: "#667eea",
                    textDecoration: "none",
                  }}
                >
                  View Listing →
                </a>
              </>
            );
          }
          return part ? <span key={`text-${index}`}>{part}</span> : null;
        })}
      </>
    );
  };

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendRequest = async (prompt) => {
    const payload = {
      query: { prompt },
      session_input: { session_id: sessionId },
    };

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      throw new Error(`API Error: ${error.message}`);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Add context based on menu selection
    let prompt = input;
    if (activeMenu === "property") {
      prompt = `[PROPERTY SEARCH] ${input}`;
    } else if (activeMenu === "location") {
      prompt = `[LOCATION INFO] ${input}`;
    } else if (activeMenu === "email") {
      prompt = `[EMAIL WRITING] ${input}`;
    }

    // Add user message to current menu's chat
    const userMessage = {
      id: menuChats[activeMenu].length + 1,
      text: input,
      sender: "user",
      timestamp: new Date(),
    };

    setMenuChats((prev) => ({
      ...prev,
      [activeMenu]: [...prev[activeMenu], userMessage],
    }));
    setInput("");
    setLoading(true);

    try {
      const data = await sendRequest(prompt);
      const botMessage = {
        id: menuChats[activeMenu].length + 2,
        text: data.result || "No response from agent",
        sender: "bot",
        timestamp: new Date(),
        agent: data.agent,
      };
      setMenuChats((prev) => ({
        ...prev,
        [activeMenu]: [...prev[activeMenu], botMessage],
      }));
    } catch (error) {
      const errorMessage = {
        id: menuChats[activeMenu].length + 2,
        text: `Error: ${error.message}`,
        sender: "bot",
        timestamp: new Date(),
        isError: true,
      };
      setMenuChats((prev) => ({
        ...prev,
        [activeMenu]: [...prev[activeMenu], errorMessage],
      }));
    } finally {
      setLoading(false);
    }
  };

  // Clear current menu's chat
  const clearChat = () => {
    const initialMessage = menuChats[activeMenu][0];
    setMenuChats((prev) => ({
      ...prev,
      [activeMenu]: [initialMessage],
    }));
  };

  return (
    <div className="app-container">
      <div className="chat-container">
        {/* Header */}
        <div className="chat-header">
          <h1>🏠 Real Estate Agent</h1>
          <div className="session-control">
            <label>Session ID:</label>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="Enter session ID"
              className="session-input"
            />
          </div>
        </div>

        {/* Menu Buttons */}
        <div className="menu-buttons">
          <button
            className={`menu-btn ${activeMenu === "chat" ? "active" : ""}`}
            onClick={() => setActiveMenu("chat")}
          >
            💬 General Chat
          </button>
          <button
            className={`menu-btn ${activeMenu === "property" ? "active" : ""}`}
            onClick={() => setActiveMenu("property")}
          >
            🏠 Property Search
          </button>
          <button
            className={`menu-btn ${activeMenu === "location" ? "active" : ""}`}
            onClick={() => setActiveMenu("location")}
          >
            📍 Location Info
          </button>
          <button
            className={`menu-btn ${activeMenu === "email" ? "active" : ""}`}
            onClick={() => setActiveMenu("email")}
          >
            ✉️ Email Writer
          </button>
          <button className="menu-btn clear-btn" onClick={clearChat}>
            🗑️ Clear Chat
          </button>
        </div>

        {/* Messages Area */}
        <div className="messages-container">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message ${msg.sender} ${msg.isError ? "error" : ""}`}
            >
              <div className="message-content">
                {msg.agent && (
                  <div className="message-agent">
                    <strong>{msg.agent}</strong>
                  </div>
                )}
                <div className="message-text">{formatMessage(msg.text)}</div>
              </div>
              <span className="message-time">
                {msg.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          ))}
          {loading && (
            <div className="message bot loading">
              <div className="message-content">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <form className="input-form" onSubmit={handleSendMessage}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message here..."
            disabled={loading}
            className="message-input"
          />
          <button type="submit" disabled={loading} className="send-btn">
            {loading ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
