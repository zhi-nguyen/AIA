/**
 * ChatWindow.tsx - Khung chat chính
 * Hiển thị danh sách tin nhắn và ô nhập
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import MessageBubble from "@/components/MessageBubble";

export default function ChatWindow() {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom khi có tin nhắn mới
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    send(input);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header__left">
          <div className="chat-header__avatar">A</div>
          <div>
            <h1 className="chat-header__title">AIA - Trợ Lý AI</h1>
            <p className="chat-header__subtitle">
              {isLoading ? "Đang suy nghĩ..." : "Online"}
            </p>
          </div>
        </div>
        <button
          className="chat-header__clear"
          onClick={clearMessages}
          title="Xóa lịch sử chat"
        >
          Clear
        </button>
      </header>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty__icon">AIA</div>
            <h2>Xin chào! Tôi là AIA</h2>
            <p>Trợ lý AI cá nhân của bạn. Hãy hỏi tôi bất cứ điều gì!</p>
            <div className="chat-empty__suggestions">
              <button onClick={() => send("Có mail nào mới không?")}>
                Kiểm tra email
              </button>
              <button onClick={() => send("Có tin gì về AI hôm nay không?")}>
                Tin tức AI
              </button>
              <button onClick={() => send("Giúp tôi lên kế hoạch làm việc hôm nay")}>
                Lên kế hoạch
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Error message */}
        {error && (
          <div className="chat-error">
            Lỗi: {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-container">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập tin nhắn... (Enter để gửi, Shift+Enter để xuống dòng)"
          rows={1}
          disabled={isLoading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          {isLoading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
