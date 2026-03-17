/**
 * api.ts - API Client cho AIA Backend
 * Giao tiếp với FastAPI backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// === Types ===

export interface ChatRequest {
  message: string;
  user_id?: string;
}

export interface ChatResponse {
  response: string;
  route: string | null;
  route_reasoning: string | null;
}

export interface UserProfile {
  user_id: string;
  name: string;
  occupation?: string;
  interests?: string[];
  preferred_news_sources?: string[];
  work_style?: string;
}

export interface GraphInfo {
  nodes: string[];
  flow: string;
  version: string;
}

// === API Functions ===

/**
 * Gửi tin nhắn đến AI và nhận response
 */
export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: request.message,
      user_id: request.user_id || "default_user",
    }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Tạo user profile
 */
export async function createUserProfile(profile: UserProfile): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/user/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Lấy profile người dùng đã lưu
 */
export async function getUserProfile(userId: string = "default_user"): Promise<{ status: string; profile: UserProfile | null; message?: string }> {
  const res = await fetch(`${API_BASE_URL}/user/profile?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Lấy thông tin graph hiện tại
 */
export async function getGraphInfo(): Promise<GraphInfo> {
  const res = await fetch(`${API_BASE_URL}/graph/info`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Health check backend
 */
export async function healthCheck(): Promise<{ status: string; service: string }> {
  const res = await fetch("http://localhost:8000/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
