"use client";

import React, { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { uploadFile, uploadImage, clearDocument, type UploadResult } from "@/lib/api";
import { X, Send, Bot, Mail, Newspaper, FileText, Paperclip, Mic, Square, Hourglass, User, Volume2 } from "lucide-react";

interface AgentChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

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

export default function AgentChatPanel({ isOpen, onClose }: AgentChatPanelProps) {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const { isRecording, isProcessing, voiceError, startRecording, stopRecording } = useVoice();
  
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ttsVolume, setTtsVolume] = useState<number>(1.0);

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

  // Focus input khi panel được mở
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

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
    // Focus vào input để nhập message
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
          await uploadImage(pendingFile);
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

  const canSend = (input.trim().length > 0 || pendingFile !== null) && !isLoading && !isUploading;

  return (
    <div className={`absolute top-0 right-0 h-full w-[450px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col transition-transform duration-300 ease-in-out ${isOpen ? "translate-x-0" : "translate-x-full"}`}>
      {/* Header */}
      <div className="flex justify-between items-center bg-white border-b border-slate-100 p-5 shrink-0 shadow-sm z-10 relative">
        <h2 className="font-bold text-slate-800 flex items-center gap-2 text-lg">
          <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-sm shadow-emerald-500/50"></span>
          Agent Chatbox
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center" title="Âm lượng đọc tự động (TTS)">
            <Volume2 size={16} className="text-slate-400 mr-2" />
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={ttsVolume} 
              onChange={(e) => setTtsVolume(parseFloat(e.target.value))} 
              className="w-16 accent-indigo-500 cursor-pointer"
            />
          </div>
          <button type="button" onClick={onClose} className="p-2 text-slate-400 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 rounded-xl transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Document badge (đã upload trước đó) */}
      {attachedDoc && (
        <div className="px-5 pt-4 pb-2 border-b border-slate-100 flex items-center justify-between text-sm bg-indigo-50/50">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="p-1.5 bg-indigo-100 text-indigo-600 rounded">
              <FileText size={16} />
            </div>
            <span className="font-semibold text-slate-700 truncate">{attachedDoc.filename}</span>
            <span className="text-xs text-slate-500 shrink-0">
              ({attachedDoc.char_count.toLocaleString()} ký tự{attachedDoc.truncated && ", đã cắt"})
            </span>
          </div>
          <button type="button" onClick={handleClearDoc} className="p-1 text-slate-400 hover:text-red-500 transition-colors ml-2">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Error messages */}
      {(error || voiceError || uploadError) && (
        <div className="px-5 py-3 bg-red-50 border-b border-red-100 text-red-600 text-sm flex flex-col gap-1">
          {error && <div>Lỗi: {error}</div>}
          {voiceError && <div>🎤 {voiceError}</div>}
          {uploadError && <div>📎 {uploadError}</div>}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-6 p-6 custom-scrollbar bg-slate-50/80">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-4">
            <Bot size={48} className="text-indigo-200" />
            <p className="text-sm font-medium">Hãy hỏi tôi bất cứ điều gì!</p>
            <div className="flex flex-col gap-2 w-full max-w-[280px]">
              <button type="button" onClick={() => send("Có mail nào mới không?")} className="px-4 py-2 bg-white border border-slate-200 rounded-xl hover:border-indigo-300 hover:text-indigo-600 transition-colors text-sm font-medium flex items-center justify-center gap-2 shadow-sm">
                <Mail size={16} /> Kiểm tra email
              </button>
              <button type="button" onClick={() => send("Có tin gì về AI hôm nay không?")} className="px-4 py-2 bg-white border border-slate-200 rounded-xl hover:border-indigo-300 hover:text-indigo-600 transition-colors text-sm font-medium flex items-center justify-center gap-2 shadow-sm">
                <Newspaper size={16} /> Tin tức AI
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-md ${msg.role === 'user' ? 'bg-indigo-500 shadow-indigo-500/30 border border-indigo-400' : 'bg-slate-800'}`}>
              {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
            </div>
            <div className={`p-4 rounded-2xl text-[13px] shadow-sm leading-relaxed max-w-[85%] font-medium whitespace-pre-wrap break-words
              ${msg.role === 'user' 
                ? 'bg-[#1e1e2d] text-white rounded-tr-sm shadow-lg' 
                : 'bg-white border border-slate-100 text-slate-800 rounded-tl-sm'}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-3">
             <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 shadow-md">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="p-4 rounded-2xl bg-white border border-slate-100 text-slate-800 rounded-tl-sm text-[13px] shadow-sm flex items-center gap-2">
                <Hourglass className="w-4 h-4 animate-spin text-indigo-500" /> <span className="text-slate-500 italic">Đang suy nghĩ...</span>
              </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="bg-white border-t border-slate-100 shrink-0 flex flex-col relative pb-4 px-5 pt-4">
        {/* Pending File Preview (hiển thị nổi trên input một chút hoặc gắn liền) */}
        {pendingFile && (
          <div className="mb-3 p-3 bg-indigo-50/50 border border-indigo-100 rounded-xl flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3 overflow-hidden">
              {pendingFileType === "image" && pendingPreview ? (
                <img src={pendingPreview} alt={pendingFile.name} className="w-10 h-10 object-cover rounded-lg border border-indigo-200" />
              ) : (
                 <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center shrink-0">
                   <FileText size={20} />
                 </div>
              )}
              <div className="flex flex-col flex-1 min-w-0">
                <span className="text-sm font-semibold text-slate-800 truncate">{pendingFile.name}</span>
                <span className="text-xs text-slate-500">{formatFileSize(pendingFile.size)}</span>
              </div>
            </div>
            <button onClick={handleClearPending} className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors shrink-0">
              <X size={16} />
            </button>
          </div>
        )}

        <div className="relative flex flex-col gap-2 shadow-sm rounded-2xl border border-slate-200 bg-slate-50 focus-within:ring-2 focus-within:ring-indigo-500/40 focus-within:border-indigo-500 transition-all p-1">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.gif,.webp"
            onChange={handleFileSelect}
            style={{ display: "none" }}
          />

          <div className="flex items-center px-1">
             <input
               ref={inputRef}
               type="text"
               value={input}
               onChange={(e) => setInput(e.target.value)}
               onKeyDown={handleKeyDown}
               placeholder={
                 pendingFile 
                   ? "Nhập tin nhắn kèm file..." 
                   : isRecording 
                     ? "Đang ghi âm... nhấn ⏹ để dừng" 
                     : "Ví dụ: Gắn mác quan trọng cho..."
               }
               disabled={isLoading || isRecording || isUploading}
               className="w-full bg-transparent py-3 px-3 text-sm focus:outline-none text-slate-800 placeholder:text-slate-400 disabled:opacity-50"
             />
          </div>
          
          <div className="flex items-center justify-between px-2 pb-2">
            <div className="flex items-center gap-1">
              <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading || isUploading}
                className={`p-2 rounded-lg transition-colors ${isUploading ? 'text-indigo-500 bg-indigo-50' : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'} disabled:opacity-50`}
                title="Đính kèm tài liệu, hình ảnh"
              >
                <Paperclip size={18} />
              </button>
              <button 
                onClick={handleVoiceToggle}
                disabled={isLoading || isProcessing}
                className={`p-2 rounded-lg transition-colors ${isRecording ? 'text-red-500 bg-red-50 animate-pulse' : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'} disabled:opacity-50`}
                title={isRecording ? "Dừng ghi âm" : "Ghi âm giọng nói"}
              >
                {isRecording ? <Square size={18} className="fill-current" /> : <Mic size={18} />}
              </button>
            </div>
            
            <button 
              onClick={handleSend}
              disabled={!canSend}
              className="px-4 py-2 bg-indigo-500 text-white rounded-xl hover:bg-indigo-600 active:scale-95 transition-all shadow-md shadow-indigo-500/30 flex items-center justify-center gap-2 font-medium disabled:opacity-50 disabled:active:scale-100 disabled:cursor-not-allowed"
            >
              {isLoading || isUploading ? <Hourglass className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
