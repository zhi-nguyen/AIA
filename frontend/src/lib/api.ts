/**
 * api.ts - API Client cho AIA Backend
 * Giao tiếp với FastAPI backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  return fetch(url, { ...options, credentials: "include" });
}

export async function initSession(): Promise<{ status: string; user_id: string; role: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/auth/session`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

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
  user_id?: string;
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

export interface SendMessageResponse {
  task_id: string;
  status: string;
}

/**
 * Gửi tin nhắn đến AI và nhận response
 */
export async function sendMessage(request: ChatRequest): Promise<SendMessageResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: request.message,
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
  const res = await fetchWithAuth(`${API_BASE_URL}/user/profile`, {
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
export async function getUserProfile(): Promise<{ status: string; profile: UserProfile | null; message?: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/user/profile`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Lấy URL đăng nhập Google
 */
export async function getGoogleAuthUrl(): Promise<{ status: string; url: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/auth/google/login`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Lấy thông tin graph hiện tại
 */
export async function getGraphInfo(): Promise<GraphInfo> {
  const res = await fetchWithAuth(`${API_BASE_URL}/graph/info`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Health check backend
 */
export async function healthCheck(): Promise<{ status: string; service: string }> {
  const res = await fetchWithAuth("http://localhost:8000/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Chuyển đổi text thành audio (TTS)
 * Trả về audio blob (WAV)
 */
export async function synthesizeSpeech(text: string): Promise<Blob> {
  const res = await fetchWithAuth(`${API_BASE_URL}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "TTS error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  const taskResponse = await res.json();
  const taskId = taskResponse.task_id;

  return new Promise((resolve, reject) => {
    const handleTts = async (e: Event) => {
      const customEvent = e as CustomEvent;
      const data = customEvent.detail;
      window.removeEventListener(`tts_response_${taskId}`, handleTts);

      if (data.error) {
        return reject(new Error(data.error));
      }

      let base64Str = data.audio_base64;
      // Remove any whitespace or newlines that might cause atob to fail
      base64Str = base64Str.replace(/\s+/g, "");
      // Just in case a data URI prefix was accidentally included
      base64Str = base64Str.replace(/^data:audio\/\w+;base64,/, "");
      
      try {
        // Use native fetch API to decode base64, much more robust than atob()
        const fetchRes = await fetch(`data:audio/wav;base64,${base64Str}`);
        resolve(await fetchRes.blob());
      } catch (err) {
        // Fallback robust atob if necessary
        try {
          const cleanStr = base64Str.replace(/-/g, '+').replace(/_/g, '/');
          const binaryStr = window.atob(cleanStr);
          const bytes = new Uint8Array(binaryStr.length);
          for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          resolve(new Blob([bytes], { type: "audio/wav" }));
        } catch (atobErr) {
          reject(atobErr);
        }
      }
    };
    window.addEventListener(`tts_response_${taskId}`, handleTts);
  });
}

/**
 * Chuyển đổi audio thành text (STT)
 * Gửi audio file, nhận lại text đã nhận dạng
 */
export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");

  const res = await fetchWithAuth(`${API_BASE_URL}/stt`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "STT error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  const data: { text: string; success: boolean } = await res.json();
  return data.text;
}

// === File Upload ===

export interface UploadResult {
  success: boolean;
  filename: string;
  format: string;
  char_count: number;
  truncated: boolean;
  preview: string;
}

export interface DocumentStatus {
  has_document: boolean;
  filename?: string;
  format?: string;
  char_count?: number;
}

/**
 * Upload file document (PDF, DOCX, CSV, XLSX...)
 */
export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetchWithAuth(`${API_BASE_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Xóa document đã upload
 */
export async function clearDocument(): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE_URL}/upload`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

/**
 * Kiểm tra trạng thái document
 */
export async function getDocumentStatus(): Promise<DocumentStatus> {
  const res = await fetchWithAuth(`${API_BASE_URL}/upload/status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// === Image Upload ===

export interface ImageUploadResult {
  success: boolean;
  filename: string;
  description: string;
}

/**
 * Upload ảnh (PNG, JPG, JPEG, GIF, WEBP)
 * Backend dùng Gemini Vision để mô tả nội dung ảnh
 */
export async function uploadImage(file: File): Promise<ImageUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetchWithAuth(`${API_BASE_URL}/upload/image`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload error" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}
/**
 * Tải xuống script Local Agent
 */
export async function downloadAgentScript(): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE_URL}/agent/download`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Download failed" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;

  let filename = "AIA_Setup.zip";
  const disposition = res.headers.get("Content-Disposition");
  if (disposition && disposition.includes("attachment")) {
    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
    const matches = filenameRegex.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, "");
    }
  }

  a.download = filename;
  document.body.appendChild(a);
  a.click();

  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Tạo token mới cho Local Agent
 */
export async function provisionAgentToken(): Promise<{ status: string; token: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/agent/token`, { method: "POST" });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Token provisioning failed" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Execute a proposal (send email + optionally save to calendar)
 */
export async function executeProposal(payload: {
  subject: string;
  body: string;
  recipients: string[];
  event_id?: string;
  proposed_time?: string;
}): Promise<{ status: string; message_id?: string; event_id?: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/execute-proposal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to execute proposal" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Lấy danh sách Proposal đang pending từ DB (nếu reload trang)
 */
export async function getProposals(): Promise<any> {
  const res = await fetchWithAuth(`${API_BASE_URL}/proposals`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch proposals" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Xóa Proposal khỏi DB sau khi đã xử lý (Gửi / Bỏ qua)
 */
export async function deleteProposal(proposalId: string): Promise<{ status: string; deleted: boolean }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/proposals/${proposalId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete proposal" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
