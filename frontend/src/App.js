import React, { useState, useRef, useEffect } from "react";
import "./App.css";

function App() {
  const [sessionId, setSessionId] = useState("default");
  const [menuLoading, setMenuLoading] = useState({chat: false, property: false, location: false, email: false});
  const [menuLoadingMsg, setMenuLoadingMsg] = useState({chat: "", property: "", location: "", email: ""});
  const [activeMenu, setActiveMenu] = useState("chat");
  const STARTER_CHIPS = {
    chat: ["What's the market like in London?", "Find me a flat in Reading under £1500", "Help me write an email to a landlord"],
    property: ["2-bed flat in Reading under £1500", "Studio in Manchester under £900", "Rooms in London E1 under £800", "Houses in Bristol under £2000"],
    location: ["Tell me about RG1 area", "What's near Reading hospital?", "Compare Manchester vs Leeds for renting"],
    email: ["Email landlord asking about availability", "Email agent to book a viewing this weekend", "Email follow-up after a viewing"],
  };
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [livePartial, setLivePartial] = useState("");
  const [showSessionTip, setShowSessionTip] = useState(false);
  const [tipPos, setTipPos] = useState({top: 0, left: 0});
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const loading = menuLoading[activeMenu];
  const loadingMsg = menuLoadingMsg[activeMenu];
  const setLoading = (val) => setMenuLoading(prev => ({...prev, [activeMenu]: val}));
  const setLoadingMsg = (val) => setMenuLoadingMsg(prev => ({...prev, [activeMenu]: val})); // 'chat', 'property', 'location', 'email'

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

  const API_URL = "https://realestate-agent-1r07.onrender.com/realestate-agent";

  // Format message text with markdown and links
  const formatMessage = (text) => {
    if (!text) return null;

    // Split by newlines, then group listing cards
    const lines = text.split("\n");
    const formatted = [];
    let inCard = false;
    let cardLines = [];

    const flushCard = (key) => {
      if (cardLines.length === 0) return;
      const cardContent = cardLines.map((ln, i) => {
        const t = ln.trim();
        const kv = t.match(/^([💰🛏📍🔗🏢])\s+(.+)$/);
        if (kv) {
          // Strip [WHY:...] for display, save for tooltip
          let displayText = kv[2];
          let whyText = "";
          const whyMatch = displayText.match(/\[WHY:([^\]]+)\]/);
          if (whyMatch) {
            whyText = whyMatch[1];
            displayText = displayText.replace(/\s*\[WHY:[^\]]+\]/, "");
          }
          return (
            <div key={i} style={{margin: "4px 0", display: "flex", alignItems: "flex-start", gap: "6px"}}>
              <span style={{fontSize: "14px"}}>{kv[1]}</span>
              <span style={{flex: 1, fontSize: "13px"}}>
                {formatLineContent(displayText)}
                {whyText && (
                  <span
                    title={whyText}
                    style={{marginLeft: "6px", cursor: "help", color: "#7a8c5c", fontSize: "11px", borderBottom: "1px dotted #7a8c5c"}}
                  >
                    ⓘ why?
                  </span>
                )}
              </span>
            </div>
          );
        }
        if (t.startsWith("**") && t.endsWith("**")) {
          return <div key={i} style={{fontWeight: 700, fontSize: "14.5px", marginBottom: "6px", color: "#2a2a2a"}}>{t.replace(/\*\*/g, "")}</div>;
        }
        return <div key={i}>{formatLineContent(t)}</div>;
      });
      formatted.push(
        <div key={key} style={{
          background: "#fff", border: "1px solid #ebe5d2", borderRadius: "10px",
          padding: "14px 16px", margin: "8px 0", boxShadow: "0 1px 3px rgba(60,50,30,0.06)",
          transition: "transform 0.15s, box-shadow 0.15s",
        }}
        onMouseOver={e => {e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 6px 16px rgba(60,50,30,0.1)";}}
        onMouseOut={e => {e.currentTarget.style.transform = ""; e.currentTarget.style.boxShadow = "0 1px 3px rgba(60,50,30,0.06)";}}
        >
          {cardContent}
        </div>
      );
      cardLines = [];
    };

    lines.forEach((line, index) => {
      let trimmed = line.trim();

      if (trimmed === "--LISTING-START--") { inCard = true; cardLines = []; return; }
      if (trimmed === "--LISTING-END--") { inCard = false; flushCard(`card-${index}`); return; }
      if (inCard) { cardLines.push(line); return; }

      // Horizontal rule
      if (/^---+$/.test(trimmed) || /^━+$/.test(trimmed)) {
        formatted.push(<hr key={index} style={{border: 0, borderTop: "1px solid #e0e0e0", margin: "8px 0"}} />);
        return;
      }

      // H3 heading (### Title)
      if (trimmed.startsWith("### ")) {
        const content = trimmed.substring(4);
        formatted.push(
          <h3 key={index} style={{fontSize: "16px", fontWeight: "700", margin: "12px 0 4px", color: "#333"}}>
            {formatLineContent(content)}
          </h3>
        );
        return;
      }

      // H2 heading (## Title)
      if (trimmed.startsWith("## ")) {
        const content = trimmed.substring(3);
        formatted.push(
          <h2 key={index} style={{fontSize: "18px", fontWeight: "700", margin: "14px 0 6px", color: "#222"}}>
            {formatLineContent(content)}
          </h2>
        );
        return;
      }

      // Asterisk-style heading: *Subject:* or **Subject:** or *Subject: text
      if (trimmed.startsWith("*") && !trimmed.startsWith("* ")) {
        // Strip ALL leading/trailing asterisks
        let cleaned = trimmed.replace(/^\*+/, "").replace(/\*+$/, "").trim();
        formatted.push(
          <p key={index} style={{fontWeight: "bold", marginTop: "10px", marginBottom: "4px", fontSize: "15px", color: "#2a2a2a"}}>
            {formatLineContent(cleaned)}
          </p>
        );
        return;
      }

      // Bullet points
      if (trimmed.match(/^[•\-*]\s/)) {
        const content = trimmed.replace(/^[•\-*]\s+/, "");
        formatted.push(
          <p key={index} style={{marginLeft: "12px", margin: "2px 0 2px 12px"}}>
            • {formatLineContent(content)}
          </p>
        );
        return;
      }

      // Key-value lines (Type: ..., Rent: ..., Link: ...)
      const kvMatch = trimmed.match(/^([A-Z][A-Za-z ]{1,20}):\s+(.+)$/);
      if (kvMatch) {
        formatted.push(
          <p key={index} style={{margin: "1px 0", lineHeight: "1.4"}}>
            <strong>{kvMatch[1]}:</strong> {formatLineContent(kvMatch[2])}
          </p>
        );
        return;
      }

      // Regular text — tight spacing
      if (trimmed) {
        formatted.push(<p key={index} style={{margin: "2px 0", lineHeight: "1.4"}}>{formatLineContent(line)}</p>);
      } else {
        formatted.push(<div key={index} style={{height: "4px"}} />);
      }
    });

    return <div>{formatted}</div>;
  };

  // Highlight [placeholder] text in a subtle pill style
  const formatPlaceholders = (text) => {
    if (typeof text !== "string" || !text.includes("[")) return text;
    const parts = text.split(/(\[[^\]]+\])/g);
    return parts.map((p, i) =>
      /^\[[^\]]+\]$/.test(p) ? (
        <span key={i} style={{
          background: "rgba(180, 130, 90, 0.12)",
          color: "#8b4513",
          padding: "1px 6px",
          borderRadius: "4px",
          fontSize: "0.92em",
          fontWeight: 500,
        }}>{p.slice(1, -1)}</span>
      ) : p
    );
  };

  // Format a single line: bold (**), italic (*..*), placeholders, links
  const formatLineContent = (text) => {
    if (!text) return null;

    // 1. Bold: **text**
    const boldParts = text.split("**");
    if (boldParts.length > 1) {
      return (
        <>
          {boldParts.map((part, i) =>
            i % 2 === 1
              ? <strong key={i}>{formatItalicAndLinks(part)}</strong>
              : <React.Fragment key={i}>{formatItalicAndLinks(part)}</React.Fragment>
          )}
        </>
      );
    }
    return formatItalicAndLinks(text);
  };

  // Inline italic *text* + links + placeholders
  const formatItalicAndLinks = (text) => {
    if (!text || typeof text !== "string") return text;
    // split on single asterisks NOT followed/preceded by another asterisk
    const parts = text.split(/(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)/);
    return parts.map((p, i) => {
      if (i % 2 === 1) {
        return <em key={i} style={{color: "#5a6b48"}}>{formatPlaceholders(p)}</em>;
      }
      const linkified = formatTextWithLinks(p);
      // if linkified is a string, also apply placeholder formatting
      if (typeof linkified === "string") return <React.Fragment key={i}>{formatPlaceholders(linkified)}</React.Fragment>;
      return <React.Fragment key={i}>{linkified}</React.Fragment>;
    });
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


  const sendStreamingRequest = async (prompt, onChunk) => {
    const payload = {
      query: { prompt },
      session_input: { session_id: sessionId },
    };
    const response = await fetch("https://realestate-agent-1r07.onrender.com/property-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onChunk(data);
          } catch (e) {}
        }
      }
    }
  };


  const startRecording = async () => {
    // Force-close any leftover session first
    if (mediaRecorderRef.current) {
      stopRecording();
      await new Promise(r => setTimeout(r, 300));
    }
    setLivePartial("");
    try {
      // 1. Get temporary JWT from backend
      const jwtResp = await fetch("https://realestate-agent-1r07.onrender.com/speechmatics-jwt", { method: "POST" });
      const { jwt } = await jwtResp.json();
      if (!jwt) throw new Error("No JWT received");

      // 2. Open WebSocket to Speechmatics RT
      const ws = new WebSocket(`wss://eu2.rt.speechmatics.com/v2?jwt=${jwt}`);
      mediaRecorderRef.current = { ws };

      ws.onopen = async () => {
        // 3. Set up mic + audio processing FIRST to learn actual sample rate
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
        });
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const actualSampleRate = audioCtx.sampleRate;
        console.log("[Speechmatics] Actual sample rate:", actualSampleRate);

        // Tell Speechmatics the ACTUAL sample rate the browser is using
        ws.send(JSON.stringify({
          message: "StartRecognition",
          audio_format: { type: "raw", encoding: "pcm_s16le", sample_rate: actualSampleRate },
          transcription_config: { language: "en", enable_partials: true, max_delay: 2 },
        }));

        const source = audioCtx.createMediaStreamSource(stream);
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);

        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const float32 = e.inputBuffer.getChannelData(0);
          // Convert Float32 → Int16 PCM
          const int16 = new Int16Array(float32.length);
          for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          ws.send(int16.buffer);
        };

        source.connect(processor);
        processor.connect(audioCtx.destination);
        mediaRecorderRef.current = { ws, stream, audioCtx, processor };
        setIsRecording(true);
      };

      // 4. Handle transcripts as they stream in
      let finalText = "";
      let silenceTimer = null;
      let submitted = false;

      const tryVoiceCommand = (text) => {
        // normalize: lowercase, strip punctuation, collapse whitespace
        const lower = text.toLowerCase().replace(/[.,!?]/g, "").replace(/\s+/g, " ").trim();
        console.log("[VoiceCmd] checking:", lower);
        if (/(clear|reset|empty)( the)? chat/.test(lower)) { clearChat(); return true; }
        if (/switch to (property|search)/.test(lower)) { setActiveMenu("property"); return true; }
        if (/switch to (location|info)/.test(lower)) { setActiveMenu("location"); return true; }
        if (/switch to (email|writer)/.test(lower)) { setActiveMenu("email"); return true; }
        if (/switch to (chat|general)/.test(lower)) { setActiveMenu("chat"); return true; }
        return false;
      };

      const autoSubmit = () => {
        if (submitted) return;
        const text = finalText.trim();
        if (!text) return;
        submitted = true;
        console.log("[AutoSubmit] submitting:", text);
        const textToSubmit = text;
        finalText = "";
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
        stopRecording();
        // Ensure input has the final text, then submit the form (uses fresh closure)
        setInput(textToSubmit);
        setTimeout(() => {
          const form = document.querySelector(".input-form");
          if (form) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.click();
          }
        }, 100);
      };

      const resetSilenceTimer = () => {
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(autoSubmit, 1800); // 2.5s silence → auto submit
      };

      ws.onmessage = (evt) => {
        if (submitted) return;
        const msg = JSON.parse(evt.data);
        if (msg.message === "AddPartialTranscript") {
          const partial = msg.metadata?.transcript || "";
          setLivePartial(partial);
          if (partial.trim()) resetSilenceTimer();
        } else if (msg.message === "AddTranscript") {
          const t = msg.metadata?.transcript || "";
          if (t.trim()) {
            finalText = (finalText + " " + t).trim() + " ";
            // Check voice commands first
            if (tryVoiceCommand(finalText)) {
              finalText = "";
              setInput("");
              setLivePartial("");
              if (silenceTimer) clearTimeout(silenceTimer);
              stopRecording();
              return;
            }
            setInput(finalText);
            setLivePartial("");
            resetSilenceTimer();
          }
        } else if (msg.message === "Error") {
          console.error("Speechmatics error:", msg);
        }
      };
      ws.onclose = () => {
        if (silenceTimer) clearTimeout(silenceTimer);
        setLivePartial("");
      };

      ws.onerror = (e) => console.error("WS error:", e);
    } catch (err) {
      alert("Voice setup failed: " + err.message);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    const ref = mediaRecorderRef.current;
    if (!ref) return;
    try {
      if (ref.ws && ref.ws.readyState === WebSocket.OPEN) {
        ref.ws.send(JSON.stringify({ message: "EndOfStream", last_seq_no: 0 }));
        ref.ws.close();
      }
      if (ref.processor) ref.processor.disconnect();
      if (ref.audioCtx) ref.audioCtx.close();
      if (ref.stream) ref.stream.getTracks().forEach(t => t.stop());
    } catch (e) {}
    mediaRecorderRef.current = null;
    setIsRecording(false);
    setLivePartial("");
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
    const isPropertySearch = activeMenu === "property";
    const msgs = isPropertySearch ? [
      "🔍 Searching 3 portals in parallel: Zoopla, Rightmove, SpareRoom...",
      "🌐 Bypassing anti-bot protection on each portal...",
      "📦 Fetching live listings from Zoopla...",
      "📦 Fetching live listings from Rightmove...",
      "🧠 Merging and deduplicating results...",
      "💰 Computing price-vs-market badges...",
      "✨ Almost there — assembling your results...",
    ] : ["🤔 Thinking..."];
    let i = 0;
    setLoadingMsg(msgs[0]);
    const msgInterval = setInterval(() => {
      i = (i + 1) % msgs.length;
      setLoadingMsg(msgs[i]);
    }, 6000);
    setTimeout(() => clearInterval(msgInterval), 60000);
    window._loadingInterval = msgInterval;

    try {
      if (activeMenu === "property") {
        // Use streaming endpoint - results appear as each portal completes
        const botMsgId = menuChats[activeMenu].length + 2;
        let accumulated = "";
        const portalsDone = [];
        const initialMsg = {
          id: botMsgId,
          text: "🔍 Searching Zoopla, Rightmove & SpareRoom in parallel...\n\n⏳ First results in ~20-30 seconds...",
          sender: "bot",
          timestamp: new Date(),
          agent: "Multi-Portal Search",
        };
        setMenuChats((prev) => ({
          ...prev,
          [activeMenu]: [...prev[activeMenu], initialMsg],
        }));

        await sendStreamingRequest(prompt, (data) => {
          if (data.type === "status") {
            accumulated = data.message + "\n";
          } else if (data.type === "partial") {
            accumulated += data.content + "\n";
            portalsDone.push(data.portal);
          }
          const totalPortals = 3;
          const remaining = totalPortals - portalsDone.length;
          const portalNames = ["Zoopla", "Rightmove", "SpareRoom"].filter(p => !portalsDone.includes(p));
          const suffix = data.type === "done" ? "" :
            `\n\n━━━━━━━━━━━━━━━━━━━━━\n⏳ Still fetching from: ${portalNames.join(", ")}\n━━━━━━━━━━━━━━━━━━━━━`;
          setMenuChats((prev) => ({
            ...prev,
            [activeMenu]: prev[activeMenu].map((m) =>
              m.id === botMsgId ? { ...m, text: accumulated + suffix } : m
            ),
          }));
        });
      } else {
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
      }
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
      clearInterval(window._loadingInterval);
      setLoading(false);
      setLoadingMsg("");
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
            <span style={{position: "relative", display: "inline-flex"}}>
              <span
                onMouseEnter={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  setTipPos({top: r.top + r.height/2, left: r.right + 12});
                  setShowSessionTip(true);
                }}
                onMouseLeave={() => setShowSessionTip(false)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "18px",
                  height: "18px",
                  marginLeft: "8px",
                  borderRadius: "50%",
                  background: showSessionTip ? "#7a8c5c" : "rgba(122, 140, 92, 0.12)",
                  color: showSessionTip ? "#fafaf5" : "#5a6b48",
                  cursor: "help",
                  fontSize: "11px",
                  fontWeight: 700,
                  fontFamily: "Inter, system-ui, sans-serif",
                  userSelect: "none",
                  transition: "all 0.15s",
                  transform: showSessionTip ? "scale(1.1)" : "scale(1)",
                }}
              >
                ?
              </span>
              {showSessionTip && (
                <div style={{
                  position: "fixed",
                  top: tipPos.top,
                  left: tipPos.left,
                  transform: "translateY(-50%)",
                  width: "260px",
                  padding: "10px 14px",
                  background: "#2a2a2a",
                  color: "#fafaf5",
                  fontSize: "12px",
                  lineHeight: "1.5",
                  borderRadius: "8px",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
                  zIndex: 99999,
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontWeight: 400,
                  pointerEvents: "none",
                }}>
                  Session IDs give each user their own private memory — the agent remembers your previous searches, preferences, and email drafts. Use a unique ID per person to keep conversations separate.
                </div>
              )}
            </span>
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
                {msg.sender === "bot" && activeMenu === "email" && !msg.isError && msg.text && (
                  <button
                    onClick={(e) => {
                      navigator.clipboard.writeText(msg.text);
                      const btn = e.currentTarget;
                      const orig = btn.innerText;
                      btn.innerText = "✓ Copied!";
                      setTimeout(() => { btn.innerText = orig; }, 1500);
                    }}
                    style={{
                      marginTop: "10px", padding: "6px 12px", fontSize: "12px",
                      background: "#f5f1e8", border: "1px solid #d4ccb3", borderRadius: "20px",
                      color: "#5a6b48", cursor: "pointer", fontFamily: "inherit",
                      transition: "all 0.2s"
                    }}
                    onMouseOver={e => { e.target.style.background = "#7a8c5c"; e.target.style.color = "#fafaf5"; }}
                    onMouseOut={e => { e.target.style.background = "#f5f1e8"; e.target.style.color = "#5a6b48"; }}
                  >
                    📋 Copy to clipboard
                  </button>
                )}
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
                <div style={{marginTop: "8px", fontSize: "13px", color: "#667eea", fontStyle: "italic"}}>
                  {loadingMsg}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {messages.length <= 1 && STARTER_CHIPS[activeMenu] && (
          <div style={{padding: "12px 28px", display: "flex", flexWrap: "wrap", gap: "8px", borderTop: "1px solid #e3ddc9"}}>
            <span style={{fontSize: "11px", color: "#8a8474", textTransform: "uppercase", letterSpacing: "0.1em", width: "100%", marginBottom: "4px"}}>Try asking</span>
            {STARTER_CHIPS[activeMenu].map((chip, i) => (
              <button
                key={i}
                onClick={() => {
                  setInput(chip);
                  // Wait longer for React state to flush, then submit
                  setTimeout(() => {
                    const input = document.querySelector(".message-input");
                    if (input) {
                      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                      nativeSetter.call(input, chip);
                      input.dispatchEvent(new Event("input", { bubbles: true }));
                    }
                    setTimeout(() => {
                      const form = document.querySelector(".input-form");
                      const btn = form && form.querySelector('button[type="submit"]');
                      if (btn && !btn.disabled) btn.click();
                    }, 100);
                  }, 30);
                }}
                style={{
                  padding: "6px 12px", fontSize: "12px", background: "#fff", border: "1px solid #d4ccb3",
                  borderRadius: "20px", color: "#5a6b48", cursor: "pointer", fontFamily: "inherit",
                  transition: "all 0.2s"
                }}
                onMouseOver={e => { e.target.style.background = "#7a8c5c"; e.target.style.color = "#fafaf5"; }}
                onMouseOut={e => { e.target.style.background = "#fff"; e.target.style.color = "#5a6b48"; }}
              >
                {chip}
              </button>
            ))}
          </div>
        )}
        {livePartial && (
          <div style={{padding: "6px 16px", fontSize: "13px", color: "#888", fontStyle: "italic", borderTop: "1px solid #eee", background: "#fafafa"}}>
            🎤 {livePartial}...
          </div>
        )}
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
          <button
            type="button"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={loading || isTranscribing}
            className="send-btn"
            style={{
              marginRight: "8px",
              background: isRecording ? "#ff4444" : isTranscribing ? "#ffaa00" : "#667eea",
              animation: isRecording ? "pulse 1s infinite" : "none",
            }}
            title={isRecording ? "Stop recording" : "Voice input"}
          >
            {isTranscribing ? "📝" : isRecording ? "🛑" : "🎤"}
          </button>
          <button type="submit" disabled={loading} className="send-btn">
            {loading ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
