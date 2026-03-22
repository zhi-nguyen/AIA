/**
 * ChatWindow.tsx - Khung chat chính
 * Hiển thị danh sách tin nhắn và ô nhập
 * Có nút microphone (🎤), nút đính kèm file (📎)
 * File/Image: preview trước → nhập message → gửi
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { uploadFile, uploadImage, clearDocument, type UploadResult } from "@/lib/api";
import MessageBubble from "@/components/MessageBubble";
import UserProfileForm from "@/components/UserProfileForm";

// Image extensions
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);

function getFileExtension(filename: string): string {
  const dotIdx = filename.lastIndexOf(".");
  return dotIdx >= 0 ? filename.slice(dotIdx).toLowerCase() : "";
}

function isImageFile(file: File): boolean {
  return IMAGE_EXTENSIONS.has(getFileExtension(file.name));
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ChatWindow() {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const { isRecording, isProcessing, voiceError, startRecording, stopRecording } = useVoice();
  const [input, setInput] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pending file (preview trước khi gửi)
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [pendingFileType, setPendingFileType] = useState<"document" | "image" | null>(null);

  // Upload state
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

  // Cleanup blob URL khi unmount hoặc clear pending
  useEffect(() => {
    return () => {
      if (pendingPreview && pendingPreview.startsWith("blob:")) {
        URL.revokeObjectURL(pendingPreview);
      }
    };
  }, [pendingPreview]);

  // === File select → chỉ preview, KHÔNG upload ===
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);

    if (isImageFile(file)) {
      // Image → tạo blob URL cho thumbnail preview
      const blobUrl = URL.createObjectURL(file);
      setPendingFile(file);
      setPendingPreview(blobUrl);
      setPendingFileType("image");
    } else {
      // Document → hiện icon + tên file
      setPendingFile(file);
      setPendingPreview(null);
      setPendingFileType("document");
    }

    // Reset file input để cho phép chọn lại cùng file
    if (fileInputRef.current) fileInputRef.current.value = "";
    // Focus vào textarea để nhập message
    inputRef.current?.focus();
  };

  // === Xóa file pending ===
  const handleClearPending = () => {
    if (pendingPreview && pendingPreview.startsWith("blob:")) {
      URL.revokeObjectURL(pendingPreview);
    }
    setPendingFile(null);
    setPendingPreview(null);
    setPendingFileType(null);
  };

  // === Send: upload file (nếu có) → gửi message ===
  const handleSend = async () => {
    const hasText = input.trim().length > 0;
    const hasFile = pendingFile !== null;

    if (!hasText && !hasFile) return;
    if (isLoading || isUploading) return;

    setUploadError(null);

    try {
      // Bước 1: Upload file nếu có
      if (hasFile && pendingFile) {
        setIsUploading(true);

        if (pendingFileType === "image") {
          const result = await uploadImage(pendingFile);
          // Không cần lưu doc badge cho image
        } else {
          const result = await uploadFile(pendingFile);
          setAttachedDoc(result);
        }

        handleClearPending();
        setIsUploading(false);
      }

      // Bước 2: Gửi message
      const message = hasText
        ? input.trim()
        : pendingFileType === "image"
          ? `Hãy phân tích bức ảnh tôi vừa gửi.`
          : `Tôi vừa upload file "${pendingFile?.name}". Hãy tóm tắt nội dung file.`;

      send(message);
      setInput("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi upload file";
      setUploadError(msg);
      setIsUploading(false);
    }
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

  // Clear document (đã upload trước đó)
  const handleClearDoc = async () => {
    try {
      await clearDocument();
      setAttachedDoc(null);
    } catch {
      // Silent fail
    }
  };

  // Check nếu có thể gửi
  const canSend = (input.trim().length > 0 || pendingFile !== null) && !isLoading && !isUploading;

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

      {/* Document badge (đã upload trước đó) */}
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

      {/* Input area */}
      <div className="chat-input-container">
        {/* Hidden file input — accept cả document + image */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.gif,.webp"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />

        {/* File attach button */}
        <button
          id="file-attach-btn"
          className={`file-btn ${isUploading ? "file-btn--uploading" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || isUploading}
          title="Đính kèm file hoặc ảnh"
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

        {/* Input wrapper: preview + textarea */}
        <div className="chat-input-wrapper">
          {/* File preview strip */}
          {pendingFile && (
            <div className="file-preview">
              {pendingFileType === "image" && pendingPreview ? (
                <img
                  src={pendingPreview}
                  alt={pendingFile.name}
                  className="file-preview__thumb"
                />
              ) : (
                <span className="file-preview__doc-icon">📄</span>
              )}
              <div className="file-preview__info">
                <span className="file-preview__name">{pendingFile.name}</span>
                <span className="file-preview__size">{formatFileSize(pendingFile.size)}</span>
              </div>
              <button
                className="file-preview__close"
                onClick={handleClearPending}
                title="Xóa file"
              >
                ✕
              </button>
            </div>
          )}

          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              pendingFile
                ? "Nhập tin nhắn kèm file... (hoặc Enter để gửi)"
                : isRecording
                  ? "Đang ghi âm... nhấn ⏹ để dừng"
                  : "Nhập tin nhắn... (Enter để gửi, Shift+Enter để xuống dòng)"
            }
            rows={1}
            disabled={isLoading || isRecording}
          />
        </div>

        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!canSend}
        >
          {isLoading || isUploading ? "..." : "Send"}
        </button>
      </div>

      {/* Profile Modal */}
      {showProfile && (
        <UserProfileForm onClose={() => setShowProfile(false)} />
      )}
    </div>
  );
}
