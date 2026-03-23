/**
 * MessageBubble.tsx - Component hiển thị một tin nhắn chat
 * Hỗ trợ render Markdown (bold, link, list, code...)
 * Có nút TTS (🔊) cho tin nhắn AI
 */

"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "@/hooks/useChat";
import { synthesizeSpeech } from "@/lib/api";
import { Volume2, Square, Hourglass, User, Bot, Play, Pause } from "lucide-react";

interface MessageBubbleProps {
  message: Message;
  ttsVolume?: number;
}

export default function MessageBubble({ message, ttsVolume = 1.0 }: MessageBubbleProps) {
  const isUser = message.role === "user";
  type TTSState = "idle" | "loading" | "playing" | "paused";
  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Auto-generate TTS in background when AI message is complete
  useEffect(() => {
    let isMounted = true;
    if (!isUser && message.content && !message.isLoading && !audioUrl) {
      setTtsState("loading");
      synthesizeSpeech(message.content)
        .then((blob) => {
          if (!isMounted) return;
          const url = URL.createObjectURL(blob);
          setAudioUrl(url);
          setTtsState("idle");
        })
        .catch((err) => {
          console.error("Auto TTS generation error:", err);
          if (isMounted) setTtsState("idle");
        });
    }
    return () => {
      isMounted = false;
    };
  }, [isUser, message.content, message.isLoading]);

  // Update volume dynamically
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = ttsVolume;
    }
  }, [ttsVolume]);

  // Cleanup audio object
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, [audioUrl]);

  // Phát TTS cho tin nhắn AI
  const handleTogglePlay = async () => {
    if (ttsState === "loading" || !message.content) return;

    if (ttsState === "playing") {
      if (audioRef.current) {
        audioRef.current.pause();
        setTtsState("paused");
      }
      return;
    }

    if (ttsState === "paused") {
      if (audioRef.current) {
        audioRef.current.play();
        setTtsState("playing");
      }
      return;
    }

    try {
      let playUrl = audioUrl;
      
      if (!playUrl) {
        setTtsState("loading");
        const blob = await synthesizeSpeech(message.content);
        playUrl = URL.createObjectURL(blob);
        setAudioUrl(playUrl);
      }

      if (!audioRef.current) {
        const audio = new Audio(playUrl);
        audio.volume = ttsVolume;
        audioRef.current = audio;

        audio.onended = () => setTtsState("idle");
        audio.onerror = () => setTtsState("idle");
      }

      setTtsState("playing");
      await audioRef.current.play();
    } catch (err) {
      console.error(err);
      setTtsState("idle");
    }
  };

  const handleStopTTS = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setTtsState("idle");
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
        {isUser ? <User size={20} /> : <Bot size={20} />}
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

              {/* TTS Controls — chỉ hiện cho tin nhắn AI */}
              {!isUser && message.content && (
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    id={`tts-btn-${message.id}`}
                    className={`tts-btn ${ttsState === "playing" ? "tts-btn--playing" : ""} ${ttsState === "loading" ? "tts-btn--loading" : ""}`}
                    onClick={handleTogglePlay}
                    disabled={ttsState === "loading"}
                    title={ttsState === "playing" ? "Tạm dừng" : ttsState === "loading" ? "Đang tải..." : ttsState === "paused" ? "Tiếp tục" : "Phát giọng nói"}
                  >
                    {ttsState === "loading" ? <Hourglass size={16} /> : 
                     ttsState === "playing" ? <Pause size={16} className="fill-current" /> : 
                     ttsState === "paused" ? <Play size={16} className="fill-current" /> : 
                     <Volume2 size={16} />}
                  </button>

                  {(ttsState === "playing" || ttsState === "paused") && (
                    <button
                      className="tts-btn"
                      onClick={handleStopTTS}
                      title="Dừng hẳn"
                    >
                      <Square size={16} className="fill-current" />
                    </button>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
