/**
 * useChat.ts - Custom hook quản lý trạng thái chat
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { 
  sendMessage, initSession, getChatSessions, createChatSession, 
  getSessionMessages, deleteChatSession, type ChatSession 
} from "@/lib/api";

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
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isTemporary, setIsTemporary] = useState<boolean>(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const idCounter = useRef(0);
  const ws = useRef<WebSocket | null>(null);

  // 1. WebSocket Connection
  useEffect(() => {
    let reconnectTimeout: NodeJS.Timeout;
    let isMounted = true;

    const connectWS = async () => {
      if (!isMounted) return;
      try {
        const { user_id } = await initSession();
        const wsUrl = "http://localhost:8000/api/v1".replace(/^http/, "ws") + `/ws/web/${user_id}`;
        
        const socket = new WebSocket(wsUrl);
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
              window.dispatchEvent(new CustomEvent(`tts_response_${data.task_id}`, { detail: data }));
            } else if (data.type === "new_proposal" || data.type === "NEW_PROPOSAL" || data.type === "WEATHER_ALERT") {
              window.dispatchEvent(new CustomEvent("proposal_received", { detail: data }));
            }
          } catch (e) {
            console.error("WS Parse Error", e);
          }
        };

        socket.onclose = () => {
          if (isMounted) reconnectTimeout = setTimeout(connectWS, 5000);
        };
        socket.onerror = (err) => {
          socket.close();
        };

        ws.current = socket;
      } catch (err) {
        if (isMounted) reconnectTimeout = setTimeout(connectWS, 5000);
      }
    };

    connectWS();
    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.onerror = null;
        ws.current.close();
      }
    };
  }, []);

  // 2. Tải danh sách Sessions
  const loadSessions = useCallback(async () => {
    try {
      const res = await getChatSessions();
      setSessions(res.sessions || []);
      // Nếu chưa có active sessionId và có session, tự chọn cái đầu tiên
      if (!sessionId && res.sessions && res.sessions.length > 0) {
        loadSessionMessages(res.sessions[0].id, res.sessions[0].is_temporary);
      }
    } catch (err) {
      console.error("Failed to load sessions", err);
    }
  }, [sessionId]);

  // Khởi bạp danh sách
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // 3. Chuyển/Load Session
  const loadSessionMessages = useCallback(async (id: string, temp: boolean) => {
    setSessionId(id);
    setIsTemporary(temp);
    setMessages([]);
    setError(null);
    if (temp) return; // Phiên tạm không lưu DB để load
    try {
      const res = await getSessionMessages(id);
      if (res.messages) {
        setMessages(res.messages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at)
        })));
      }
    } catch (err) {
      console.error("Failed to load messages", err);
    }
  }, []);

  // 4. Tạo Session Mới
  const startNewSession = useCallback(async (temp: boolean) => {
    try {
      if (temp) {
        const tempId = `sess-${Date.now()}`;
        setSessionId(tempId);
        setIsTemporary(true);
        setMessages([]);
      } else {
        const res = await createChatSession("Cuộc trò chuyện mới", false);
        setSessionId(res.session_id);
        setIsTemporary(false);
        setMessages([]);
        await loadSessions(); // Refresh list
      }
    } catch (err) {
      setError("Không thể tạo phiên mới");
    }
  }, [loadSessions]);

  // 5. Xóa Session
  const removeSession = useCallback(async (id: string) => {
    try {
      await deleteChatSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
      if (sessionId === id) {
        startNewSession(false);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  }, [sessionId, startNewSession]);

  const generateId = () => {
    idCounter.current += 1;
    return `msg-${Date.now()}-${idCounter.current}`;
  };

  const send = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;
      
      // Auto create DB session if one strongly required but absent
      let currentSession = sessionId;
      if (!currentSession) {
        currentSession = `sess-${Date.now()}`;
        setSessionId(currentSession);
      }

      setError(null);

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

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
          session_id: currentSession,
          is_temporary: isTemporary
        });

        // Nếu đây là tin nhắn đầu tiên của Phiên, reload list để hiển thị title
        if (messages.length === 0 && !isTemporary) {
          setTimeout(loadSessions, 1000); // Đợi DB commit
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingMessage.id ? { ...msg, taskId: response.task_id } : msg
          )
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Lỗi không xác định";
        setError(errorMsg);
        setMessages((prev) => prev.filter((msg) => msg.id !== loadingMessage.id));
        setIsLoading(false);
      }
    },
    [isLoading, sessionId, isTemporary, messages.length, loadSessions]
  );

  const clearMessages = useCallback(() => {
    startNewSession(false);
  }, [startNewSession]);

  return { 
    messages, isLoading, error, send, clearMessages, 
    sessionId, isTemporary, sessions, loadSessionMessages, startNewSession, removeSession 
  };
}
