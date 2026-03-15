/**
 * useChat.ts - Custom hook quản lý trạng thái chat
 */

"use client";

import { useState, useCallback, useRef } from "react";
import { sendMessage, type ChatResponse } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  route?: string | null;
  routeReasoning?: string | null;
  isLoading?: boolean;
}

export function useChat(userId: string = "default_user") {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idCounter = useRef(0);

  const generateId = () => {
    idCounter.current += 1;
    return `msg-${Date.now()}-${idCounter.current}`;
  };

  const send = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      setError(null);

      // Thêm tin nhắn user
      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      // Thêm placeholder loading cho AI
      const loadingMessage: Message = {
        id: generateId(),
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isLoading: true,
      };

      setMessages((prev) => [...prev, userMessage, loadingMessage]);
      setIsLoading(true);

      try {
        const response: ChatResponse = await sendMessage({
          message: content.trim(),
          user_id: userId,
        });

        // Thay thế loading message bằng response thật
        const aiMessage: Message = {
          id: loadingMessage.id,
          role: "assistant",
          content: response.response,
          timestamp: new Date(),
          route: response.route,
          routeReasoning: response.route_reasoning,
        };

        setMessages((prev) =>
          prev.map((msg) => (msg.id === loadingMessage.id ? aiMessage : msg))
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Lỗi không xác định";
        setError(errorMsg);

        // Xóa loading message khi lỗi
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== loadingMessage.id)
        );
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, userId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isLoading, error, send, clearMessages };
}
