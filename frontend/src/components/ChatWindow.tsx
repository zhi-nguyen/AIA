/**
 * ChatWindow.tsx - Khung chat chính
 * Hiển thị danh sách tin nhắn và ô nhập
 * Có nút microphone (🎤), nút đính kèm file (📎)
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { uploadFile, clearDocument, type UploadResult } from "@/lib/api";
import MessageBubble from "@/components/MessageBubble";
import UserProfileForm from "@/components/UserProfileForm";

export default function ChatWindow() {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const { isRecording, isProcessing, voiceError, startRecording, stopRecording } = useVoice();
  const [input, setInput] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Document state
  const [attachedDoc, setAttachedDoc] = useState<UploadResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  // File upload handler
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setIsUploading(true);

    try {
      const result = await uploadFile(file);
      setAttachedDoc(result);
      // Auto-send a message asking for summary
      send(`Tôi vừa upload file "${result.filename}". Hãy tóm tắt nội dung file.`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi upload file";
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      // Reset file input
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Clear document
  const handleClearDoc = async () => {
    try {
      await clearDocument();
      setAttachedDoc(null);
    } catch {
      // Silent fail
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
              {isLoading ? "Đang suy nghĩ..." : isRecording ? "🎤 Đang ghi âm..." : isProcessing ? "⏳ Đang nhận dạng..." : isUploading ? "📎 Đang tải file..." : "Online"}
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

      {/* Document badge */}
      {attachedDoc && (
        <div className="doc-badge">
          <span className="doc-badge__icon">📄</span>
          <span className="doc-badge__name">{attachedDoc.filename}</span>
          <span className="doc-badge__info">
            {attachedDoc.char_count.toLocaleString()} ký tự
            {attachedDoc.truncated && " (đã cắt)"}
          </span>
          <button className="doc-badge__close" onClick={handleClearDoc} title="Xóa tài liệu">
            ✕
          </button>
        </div>
      )}

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
              <button onClick={() => fileInputRef.current?.click()}>
                📎 Upload tài liệu
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
        {uploadError && (
          <div className="chat-error">
            📎 {uploadError}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-container">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.csv,.xlsx,.xls"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />

        {/* File attach button */}
        <button
          id="file-attach-btn"
          className={`file-btn ${isUploading ? "file-btn--uploading" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || isUploading}
          title="Đính kèm file (PDF, DOCX, CSV, XLSX)"
        >
          {isUploading ? "⏳" : "📎"}
        </button>

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
