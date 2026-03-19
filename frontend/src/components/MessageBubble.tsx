/**
 * MessageBubble.tsx - Component hiển thị một tin nhắn chat
 * Hỗ trợ render Markdown (bold, link, list, code...)
 * Có nút TTS (🔊) cho tin nhắn AI
 */

"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "@/hooks/useChat";
import { synthesizeSpeech } from "@/lib/api";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);
  const [isTTSLoading, setIsTTSLoading] = useState(false);

  // Phát TTS cho tin nhắn AI
  const handlePlayTTS = async () => {
    if (isTTSPlaying || isTTSLoading || !message.content) return;

    setIsTTSLoading(true);
    try {
      const audioBlob = await synthesizeSpeech(message.content);
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);

      audio.onplay = () => {
        setIsTTSLoading(false);
        setIsTTSPlaying(true);
      };
      audio.onended = () => {
        setIsTTSPlaying(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsTTSPlaying(false);
        setIsTTSLoading(false);
        URL.revokeObjectURL(url);
      };

      await audio.play();
    } catch {
      setIsTTSLoading(false);
      setIsTTSPlaying(false);
    }
  };

  // Route badge
  const routeBadge = message.route && !isUser && (
    <span className="route-badge" data-route={message.route}>
      {message.route === "email" && "Email"}
      {message.route === "news" && "News"}
      {message.route === "general" && "Chat"}
    </span>
  );

  return (
    <div className={`message-row ${isUser ? "message-row--user" : "message-row--ai"}`}>
      {/* Avatar */}
      <div className={`message-avatar ${isUser ? "message-avatar--user" : "message-avatar--ai"}`}>
        {isUser ? "U" : "A"}
      </div>

      {/* Bubble */}
      <div className={`message-bubble ${isUser ? "message-bubble--user" : "message-bubble--ai"}`}>
        {message.isLoading ? (
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        ) : (
          <>
            {routeBadge}
            <div className="message-content">
              {isUser ? (
                message.content
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Link mở tab mới
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                    // Code block styling
                    code: ({ children, className }) => {
                      const isInline = !className;
                      return isInline ? (
                        <code className="inline-code">{children}</code>
                      ) : (
                        <code className={className}>{children}</code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>

            {/* Footer: time + TTS button */}
            <div className="message-footer">
              <div className="message-time">
                {message.timestamp.toLocaleTimeString("vi-VN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>

              {/* TTS Button — chỉ hiện cho tin nhắn AI */}
              {!isUser && message.content && (
                <button
                  id={`tts-btn-${message.id}`}
                  className={`tts-btn ${isTTSPlaying ? "tts-btn--playing" : ""} ${isTTSLoading ? "tts-btn--loading" : ""}`}
                  onClick={handlePlayTTS}
                  disabled={isTTSPlaying || isTTSLoading}
                  title={isTTSPlaying ? "Đang phát..." : isTTSLoading ? "Đang tải..." : "Phát giọng nói"}
                >
                  {isTTSLoading ? "⏳" : isTTSPlaying ? "⏹" : "🔊"}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
