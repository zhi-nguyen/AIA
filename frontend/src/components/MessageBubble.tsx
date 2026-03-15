/**
 * MessageBubble.tsx - Component hiển thị một tin nhắn chat
 * Hỗ trợ render Markdown (bold, link, list, code...)
 */

"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "@/hooks/useChat";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

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
            <div className="message-time">
              {message.timestamp.toLocaleTimeString("vi-VN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
