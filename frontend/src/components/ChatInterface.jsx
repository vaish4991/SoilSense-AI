import { useState, useRef, useEffect } from 'react';
import { api, ApiError } from '../services/api';
import './ChatInterface.css';

const INITIAL_MESSAGE = {
  role: 'assistant',
  content: "Hello! I'm SoilSense AI 🌱 Describe your soil to me and I'll help you understand it. I'll ask follow-up questions if I need more details to make a good estimate.",
  time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
};

export default function ChatInterface({ location, targetCrop }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isTyping) return;

    const userMsg = {
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsTyping(true);

    try {
      // Build message list for API (without time field)
      const apiMessages = newMessages.map(({ role, content }) => ({ role, content }));
      const result = await api.chat(apiMessages, location, targetCrop);

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.reply,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (err) {
      const errorMsg =
        err instanceof ApiError
          ? `⚠️ ${err.message}`
          : '⚠️ Chat service temporarily unavailable. Your soil analysis still works via the form.';

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: errorMsg, time: '—' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      {isOpen && (
        <div className="chat-window" role="dialog" aria-label="SoilSense AI Chat">
          {/* Header */}
          <div className="chat-header">
            <div className="chat-header-info">
              <div className="chat-avatar">🌱</div>
              <div>
                <div className="chat-header-title">SoilSense AI</div>
                <div className="chat-header-subtitle">Soil Intelligence Assistant</div>
              </div>
            </div>
            <button
              className="chat-close-btn"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
            >
              ✕
            </button>
          </div>

          {/* Messages */}
          <div className="chat-messages" aria-live="polite">
            {messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="message-bubble">{msg.content}</div>
                {msg.time && <div className="message-time">{msg.time}</div>}
              </div>
            ))}

            {isTyping && (
              <div className="chat-message assistant">
                <div className="chat-typing">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="chat-input-area">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Describe your soil or ask a question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              aria-label="Chat input"
            />
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              aria-label="Send message"
            >
              ↑
            </button>
          </div>
        </div>
      )}

      {/* Toggle button */}
      <button
        className="chat-toggle-btn"
        onClick={() => setIsOpen((o) => !o)}
        aria-label={isOpen ? 'Close chat' : 'Open SoilSense AI chat'}
        title="Chat with SoilSense AI"
      >
        {isOpen ? '✕' : '🌱'}
      </button>
    </div>
  );
}
