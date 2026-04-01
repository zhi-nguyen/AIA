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
import { uploadFile, uploadImage, clearDocument, getGoogleAuthUrl, initSession, downloadAgentScript, provisionAgentToken, type UploadResult } from "@/lib/api";
import MessageBubble from "@/components/MessageBubble";
import UserProfileForm from "@/components/UserProfileForm";
import ProposalSidebar from "@/components/ProposalSidebar";
import CalendarSidebar from "@/components/CalendarSidebar";
import WeatherSidebar from "@/components/WeatherSidebar";
import { useProposals } from "@/hooks/useProposals";
import { Mic, Square, Hourglass, Paperclip, Settings, Trash2, FileText, X, Send, Bot, Mail, Newspaper, Volume2, Download, Key, Copy, Check, Bell, Calendar, CloudSun } from "lucide-react";

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
  const { proposals, approveProposal, dismissProposal } = useProposals();
  const { isRecording, isProcessing, voiceError, startRecording, stopRecording } = useVoice();
  const [input, setInput] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ttsVolume, setTtsVolume] = useState<number>(1.0);

  // Pending file (preview trước khi gửi)
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [pendingFileType, setPendingFileType] = useState<"document" | "image" | null>(null);

  // Unified sidebar state — chỉ 1 sidebar mở tại 1 thời điểm
  const [activeSidebar, setActiveSidebar] = useState<"calendar" | "weather" | "proposals" | null>(null);
  const prevProposalsLength = useRef(0);

  const openSidebar = (name: "calendar" | "weather" | "proposals") => {
    setActiveSidebar((prev) => (prev === name ? null : name));
  };

  const closeSidebar = () => setActiveSidebar(null);

  useEffect(() => {
    if (proposals.length > prevProposalsLength.current) {
      setActiveSidebar("proposals");
    }
    prevProposalsLength.current = proposals.length;
  }, [proposals.length]);

  // Upload state
  const [attachedDoc, setAttachedDoc] = useState<UploadResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // User state
  const [userRole, setUserRole] = useState<string>("guest");

  // Token modal state
  const [newAgentToken, setNewAgentToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Khởi tạo/check session khi tải trang
  useEffect(() => {
    initSession()
      .then(res => setUserRole(res.role))
      .catch(err => console.error("Session init failed:", err));
  }, []);

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
          <div className="chat-header__avatar"><Bot size={24} className="text-blue-400" /></div>
          <div>
            <h1 className="chat-header__title">AIA - Trợ Lý AI</h1>
            <p className="chat-header__subtitle">
              {isLoading ? "Đang suy nghĩ..." : isRecording ? "Đang ghi âm..." : isProcessing ? "Đang nhận dạng..." : isUploading ? "Đang tải file..." : "Online"}
            </p>
          </div>
        </div>
        <div className="chat-header__actions">
          {/* TTS Volume Control */}
          <div className="flex items-center mr-4" title="Âm lượng đọc tự động (TTS)">
            <Volume2 size={16} className="mr-1 opacity-70" />
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={ttsVolume} 
              onChange={(e) => setTtsVolume(parseFloat(e.target.value))} 
              style={{ width: "60px", cursor: "pointer" }}
            />
          </div>
          <button
            className="chat-header__btn"
            onClick={async () => {
              try {
                const data = await getGoogleAuthUrl();
                if (data.url) {
                  window.open(data.url, "_blank");
                }
              } catch (err) {
                console.error("Google login error:", err);
                alert("Lỗi khi lấy URL đăng nhập Google");
              }
            }}
            title="Đăng nhập Google (Gmail)"
          >
            G
          </button>
          <button
            id="profile-toggle-btn"
            className="chat-header__btn"
            onClick={() => setShowProfile(true)}
            title={userRole === "member" ? "Thiết lập thông tin cá nhân" : "Vui lòng đăng nhập Google để thiết lập thông tin"}
            disabled={userRole !== "member"}
            style={{ opacity: userRole === "member" ? 1 : 0.5, cursor: userRole === "member" ? "pointer" : "not-allowed" }}
          >
            <Settings size={20} />
          </button>
          <button
            className={`chat-header__btn ${activeSidebar === 'calendar' ? 'active text-blue-400' : ''}`}
            onClick={() => openSidebar('calendar')}
            title="Lịch hẹn cá nhân"
          >
            <Calendar size={20} />
          </button>
          <button
            className={`chat-header__btn ${activeSidebar === 'weather' ? 'active text-blue-400' : ''}`}
            onClick={() => openSidebar('weather')}
            title="Thời tiết"
          >
            <CloudSun size={20} />
          </button>
          <button
            className={`chat-header__btn ${activeSidebar === 'proposals' ? 'active text-blue-400' : ''}`}
            style={{ position: "relative" }}
            onClick={() => openSidebar('proposals')}
            title="Đề xuất & Cuộc hẹn"
          >
            <Bell size={20} />
            {proposals.length > 0 && (
              <span style={{
                position: "absolute",
                top: -5,
                right: -5,
                background: "red",
                color: "white",
                borderRadius: "50%",
                padding: "2px 6px",
                fontSize: "10px",
                fontWeight: "bold"
              }}>
                {proposals.length}
              </span>
            )}
          </button>
          {userRole === "member" && (
            <button
              className="chat-header__btn"
              onClick={async () => {
                try {
                  await downloadAgentScript();
                } catch (err) {
                  console.error("Download agent script error:", err);
                  alert("Lỗi khi tải xuống kịch bản AIA Agent.\nVui lòng chắc chắn bạn đã cấp quyền và đăng nhập.");
                }
              }}
              title="Tải xuống AIA Local Agent Script"
            >
              <Download size={20} />
            </button>
          )}
          {userRole === "member" && (
            <button
              className="chat-header__btn"
              onClick={async () => {
                try {
                  const data = await provisionAgentToken();
                  setNewAgentToken(data.token);
                  setCopied(false);
                } catch (err) {
                  console.error("Provision token error:", err);
                  alert("Lỗi khi tạo token mới.");
                }
              }}
              title="Tạo User Token mới cho AIA Local Agent"
            >
              <Key size={20} />
            </button>
          )}
          <button
            className="chat-header__btn"
            onClick={clearMessages}
            title="Xóa lịch sử chat"
          >
            <Trash2 size={20} />
          </button>
        </div>
      </header>

      {/* Document badge (đã upload trước đó) */}
      {attachedDoc && (
        <div className="doc-badge">
          <span className="doc-badge__icon"><FileText size={16} /></span>
          <span className="doc-badge__name">{attachedDoc.filename}</span>
          <span className="doc-badge__info">
            {attachedDoc.char_count.toLocaleString()} ký tự
            {attachedDoc.truncated && " (đã cắt)"}
          </span>
          <button className="doc-badge__close" onClick={handleClearDoc} title="Xóa tài liệu">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty__icon"><Bot size={48} className="text-blue-500 mx-auto" /></div>
            <h2>Xin chào! Tôi là AIA</h2>
            <p>Trợ lý AI cá nhân của bạn. Hãy hỏi tôi bất cứ điều gì!</p>
            <div className="chat-empty__suggestions">
              <button onClick={() => send("Có mail nào mới không?")}>
                <Mail size={16} className="inline mr-2" />
                Kiểm tra email
              </button>
              <button onClick={() => send("Có tin gì về AI hôm nay không?")}>
                <Newspaper size={16} className="inline mr-2" />
                Tin tức AI
              </button>
              <button onClick={() => fileInputRef.current?.click()}>
                <Paperclip size={16} className="inline mr-2" /> Upload tài liệu
              </button>
              <button 
                onClick={() => setShowProfile(true)}
                disabled={userRole !== "member"}
                title={userRole !== "member" ? "Vui lòng đăng nhập Google để thiết lập thông tin" : "Thiết lập thông tin"}
                style={{ opacity: userRole === "member" ? 1 : 0.5, cursor: userRole === "member" ? "pointer" : "not-allowed" }}
              >
                <Settings size={16} className="inline mr-2" /> Thiết lập thông tin {userRole !== "member" && "(Cần đăng nhập)"}
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} ttsVolume={ttsVolume} />
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
          {isUploading ? <Hourglass size={20} /> : <Paperclip size={20} />}
        </button>

        <button
          id="voice-record-btn"
          className={`voice-btn ${isRecording ? "voice-btn--recording" : ""} ${isProcessing ? "voice-btn--processing" : ""}`}
          onClick={handleVoiceToggle}
          disabled={isLoading || isProcessing}
          title={isRecording ? "Dừng ghi âm" : "Bắt đầu ghi âm"}
        >
          {isProcessing ? <Hourglass size={20} /> : isRecording ? <Square size={20} className="fill-current" /> : <Mic size={20} />}
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
                <span className="file-preview__doc-icon"><FileText size={24} /></span>
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
                <X size={16} />
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
          {isLoading || isUploading ? <Hourglass size={20} /> : <Send size={20} />}
        </button>
      </div>

      {/* Profile Modal */}
      {showProfile && (
        <UserProfileForm onClose={() => setShowProfile(false)} />
      )}

      {/* Token Modal */}
      {newAgentToken && (
        <div className="profile-overlay" onClick={() => setNewAgentToken(null)}>
          <div className="profile-modal" onClick={e => e.stopPropagation()}>
            <div className="profile-modal__header">
              <div>
                <h2 className="profile-modal__title">Token mới của bạn</h2>
                <p className="profile-modal__desc">Nhập token này vào cửa sổ Local Agent hoặc cập nhật trong config.json</p>
              </div>
              <button className="profile-modal__close" onClick={() => setNewAgentToken(null)} title="Đóng">
                <X size={16} />
              </button>
            </div>
            
            <div className="profile-input" style={{ wordBreak: 'break-all', fontFamily: 'monospace', userSelect: 'all', marginBottom: '8px' }}>
              {newAgentToken}
            </div>
            
            <div className="profile-actions">
              <button 
                type="button" 
                className="profile-cancel-btn"
                onClick={() => setNewAgentToken(null)}
              >
                Đóng
              </button>
              <button 
                type="button" 
                className="profile-save-btn"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                onClick={() => {
                  navigator.clipboard.writeText(newAgentToken);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "Đã Copy!" : "Copy Token"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* === SIDEBARS (tái sử dụng CSS chung, mutual exclusion) === */}
      <CalendarSidebar isOpen={activeSidebar === 'calendar'} onClose={closeSidebar} />
      <WeatherSidebar isOpen={activeSidebar === 'weather'} onClose={closeSidebar} />
      <ProposalSidebar
        isOpen={activeSidebar === 'proposals'}
        onClose={closeSidebar}
        proposals={proposals}
        onApprove={approveProposal}
        onDismiss={dismissProposal}
      />
    </div>
  );
}
