/**
 * ChatWindow.tsx - Khung chat chính
 * Hiển thị danh sách tin nhắn và ô nhập
 * Có nút microphone (🎤) để ghi âm và nhận dạng giọng nói
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import MessageBubble from "@/components/MessageBubble";
import UserProfileForm from "@/components/UserProfileForm";

export default function ChatWindow() {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const { isRecording, isProcessing, voiceError, startRecording, stopRecording } = useVoice();
  const [input, setInput] = useState("");
  const [showProfile, setShowProfile] = useState(false);
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

  // Toggle ghi âm microphone
  const handleVoiceToggle = async () => {
    if (isRecording) {
      const text = await stopRecording();
      if (text) {
        send(text);
      }
    } else {
      await startRecording();
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
              {isLoading ? "Đang suy nghĩ..." : isRecording ? "🎤 Đang ghi âm..." : isProcessing ? "⏳ Đang nhận dạng..." : "Online"}
            </p>
          </div>
        </div>
        <div className="chat-header__actions">
          <button
            id="profile-toggle-btn"
            className="chat-header__btn"
            onClick={() => setShowProfile(true)}
            title="Thiết lập thông tin cá nhân"
          >
            ⚙
          </button>
          <button
            className="chat-header__btn"
            onClick={clearMessages}
            title="Xóa lịch sử chat"
          >
            🗑
          </button>
        </div>
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
              <button onClick={() => setShowProfile(true)}>
                ⚙ Thiết lập thông tin
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Error messages */}
        {error && (
          <div className="chat-error">
            Lỗi: {error}
          </div>
        )}
        {voiceError && (
          <div className="chat-error">
            🎤 {voiceError}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-container">
        <button
          id="voice-record-btn"
          className={`voice-btn ${isRecording ? "voice-btn--recording" : ""} ${isProcessing ? "voice-btn--processing" : ""}`}
          onClick={handleVoiceToggle}
          disabled={isLoading || isProcessing}
          title={isRecording ? "Dừng ghi âm" : "Bắt đầu ghi âm"}
        >
          {isProcessing ? "⏳" : isRecording ? "⏹" : "🎤"}
        </button>
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isRecording ? "Đang ghi âm... nhấn ⏹ để dừng" : "Nhập tin nhắn... (Enter để gửi, Shift+Enter để xuống dòng)"}
          rows={1}
          disabled={isLoading || isRecording}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          {isLoading ? "..." : "Send"}
        </button>
      </div>

      {/* Profile Modal */}
      {showProfile && (
        <UserProfileForm onClose={() => setShowProfile(false)} />
      )}
    </div>
  );
}
