/**
 * useChat.ts - Custom hook quản lý trạng thái chat
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { sendMessage, initSession } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  route?: string | null;
  routeReasoning?: string | null;
  isLoading?: boolean;
  taskId?: string;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => `sess-${Date.now()}`);
  const [useLongTermMemory, setUseLongTermMemory] = useState<boolean>(false);
  
  const idCounter = useRef(0);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    let reconnectTimeout: NodeJS.Timeout;
    let isMounted = true;

    const connectWS = async () => {
      if (!isMounted) return;
      try {
        const { user_id } = await initSession();
        const wsUrl = "http://localhost:8000/api/v1".replace(/^http/, "ws") + `/ws/web/${user_id}`;
        
        const socket = new WebSocket(wsUrl);
        socket.onopen = () => {
          console.log("WS Connected");
        };
        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "chat_response") {
              setMessages((prev) => 
                prev.map((msg) => {
                  if (msg.taskId === data.task_id) {
                    return {
                      ...msg,
                      content: data.response,
                      route: data.route,
                      routeReasoning: data.route_reasoning,
                      isLoading: false
                    };
                  }
                  return msg;
                })
              );
              setIsLoading(false);
            } else if (data.type === "tts_response") {
              // Dispatch event to app layer for TTS handling
              window.dispatchEvent(new CustomEvent(`tts_response_${data.task_id}`, { detail: data }));
            } else if (data.type === "new_proposal" || data.type === "NEW_PROPOSAL") {
              // Dispatch event for useProposals hook
              window.dispatchEvent(new CustomEvent("proposal_received", { detail: data }));
            } else if (data.type === "WEATHER_ALERT") {
              // Weather alert → reuse proposal flow
              window.dispatchEvent(new CustomEvent("proposal_received", { detail: data }));
            }
          } catch (e) {
            console.error("WS Parse Error", e);
          }
        };

        socket.onclose = () => {
          console.log("WS Disconnected, reconnecting in 5s...");
          if (isMounted) {
            reconnectTimeout = setTimeout(connectWS, 5000);
          }
        };

        socket.onerror = (err) => {
          console.error("WS Error", err);
          socket.close(); // Triggers onclose and reconnects
        };

        ws.current = socket;
      } catch (err) {
        console.error("WS Connection Error", err);
        if (isMounted) {
          reconnectTimeout = setTimeout(connectWS, 5000);
        }
      }
    };

    connectWS();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      if (ws.current) {
        // Prevent reconnect loop on unmount
        ws.current.onclose = null;
        ws.current.onerror = null;
        ws.current.close();
      }
    };
  }, []);

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
        const response = await sendMessage({
          message: content.trim(),
          session_id: sessionId,
          use_long_term_memory: useLongTermMemory
        });

        // Chỉ cập nhật taskId cho loadingMessage để WS matching
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingMessage.id ? { ...msg, taskId: response.task_id } : msg
          )
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Lỗi không xác định";
        setError(errorMsg);

        // Xóa loading message khi lỗi upload/gửi
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== loadingMessage.id)
        );
        setIsLoading(false);
      }
    },
    [isLoading, sessionId, useLongTermMemory]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    setSessionId(`sess-${Date.now()}`); // Create new session
  }, []);

  return { 
    messages, isLoading, error, send, clearMessages, 
    sessionId, useLongTermMemory, setUseLongTermMemory 
  };
}
