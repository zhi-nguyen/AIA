/**
 * EmailCard.tsx — AI Secretary Meeting Proposal Card
 * Renders dynamically based on suggested_actions[] from Phase 3 AI Secretary
 * and (legacy) news_agent proposals.
 */

"use client";

import { useState } from "react";
import { CheckCircle2, Clock, Send, X, AlertCircle, Calendar, Mail, Ban, ExternalLink, CloudRain } from "lucide-react";
import type { Proposal, SuggestedAction } from "@/hooks/useProposals";

interface ProposalCardProps {
  proposal: Proposal;
  onApprove: (id: string, actionIndex?: number, modifiedPayload?: { reply_body?: string; participants?: string[]; note?: string; weather_dependent?: boolean }) => void;
  onDismiss: (id: string) => void;
}

/** Map action_type → icon */
function ActionIcon({ type }: { type: SuggestedAction["action_type"] }) {
  switch (type) {
    case "create_event":  return <Calendar size={15} />;
    case "reply_email":   return <Mail size={15} />;
    case "cancel_event":  return <CloudRain size={15} />;
    default:              return <Ban size={15} />;
  }
}

/** Confidence indicator dots */
function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 70 ? "var(--success-color, #22c55e)" : pct >= 40 ? "var(--warn-color, #f59e0b)" : "var(--muted-color, #6b7280)";
  return (
    <span className="proposal-card__confidence" style={{ color, fontSize: "0.72rem", fontWeight: 600 }}>
      {pct}% khớp
    </span>
  );
}



export default function ProposalCard({ proposal, onApprove, onDismiss }: ProposalCardProps) {
  const { id, source, status, error, timestamp } = proposal;
  const isEmailSecretary = source === "email_secretary";
  const isWeatherSystem = source === "weather_system";

  /* ── Header labels ── */
  const badge = isWeatherSystem
    ? "⛈️ Cảnh báo thời tiết"
    : isEmailSecretary
    ? "📅 Thư ký AI — Hẹn gặp"
    : "💡 Đề xuất tự động";

  /* ── Title & subtitle ── */
  const title = isWeatherSystem
    ? (proposal.event_title || "Cảnh báo thời tiết cho lịch hẹn")
    : isEmailSecretary
    ? (proposal.email_subject || "Email không có tiêu đề")
    : (proposal.title || "Đề xuất mới từ AIA");
  const subtitle = isWeatherSystem
    ? (proposal.weather_reason || "")
    : isEmailSecretary
    ? (proposal.intent || "")
    : (proposal.summary || "");

  /* ── Body detail ── */
  const fromLine = isEmailSecretary ? proposal.email_from : null;

  /* ── Actions ── */
  const actions = (isEmailSecretary || isWeatherSystem)
    ? (proposal.suggested_actions ?? [])
    : [{
        action_type: "reply_email" as const,
        label: "Duyệt & Gửi ngay",
        payload: { reply_body: proposal.payload?.body ?? "", participants: proposal.payload?.recipients ?? [] },
      }];

  /* ── State for Edit Mode ── */
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editBody, setEditBody] = useState("");
  const [editParticipants, setEditParticipants] = useState<string[]>([]);
  const [newParticipant, setNewParticipant] = useState("");
  const [editNote, setEditNote] = useState("");
  const [editWeatherDependent, setEditWeatherDependent] = useState(false);

  const handleActionClick = (idx: number, action: SuggestedAction) => {
    if (action.action_type === "ignore") {
      onApprove(id, idx);
      return;
    }
    setEditingIndex(idx);

    if (action.action_type === "cancel_event") {
      // Weather cancel: use pre-filled email from payload
      setEditBody(action.payload?.body || "");
      setEditParticipants(action.payload?.recipients || []);
      setEditNote("");
      setEditWeatherDependent(false);
      return;
    }

    const lbl = action.label.toLowerCase();
    
    // Determine user's requested prefixes based on label context
    let prefix = "";
    if (lbl.includes("đồng ý") || lbl.includes("chấp nhận")) {
      prefix = "Được ạ, ";
    } else if (lbl.includes("từ chối") || lbl.includes("bận") || lbl.includes("tiếc")) {
      prefix = "Tiếc quá, ";
    }

    const llmBody = action.payload?.reply_body || "";
    setEditBody(llmBody ? `${prefix}${llmBody}` : prefix);
    
    // Dùng participants từ action (đã chuẩn hoá ở trên thành 'participants')
    const baseParts = action.payload?.participants || [];
    let editParts = [...baseParts];
    if (proposal.email_from && !editParts.includes(proposal.email_from)) {
      editParts.push(proposal.email_from);
    }
    
    // Deduplication thông minh: Lấy ra phần ruột email (vd: abc@gmail.com) để phân biệt
    const seenEmails = new Set<string>();
    const uniqueParts: string[] = [];
    
    const extractCoreEmail = (str: string) => {
      const match = str.match(/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/i);
      return match ? match[1].toLowerCase() : str.toLowerCase();
    };

    // Ưu tiên chuỗi dài hơn (vì "Name <email@...>" chứa nhiều thông tin hơn "email@..." hoặc "Name")
    // Vậy ta sort str theo độ dài giảm dần trước khi filter
    editParts.sort((a, b) => b.length - a.length);

    for (const p of editParts) {
      const core = extractCoreEmail(p);
      // Giữ lại nếu là email duy nhất, hoặc không phải email (chỉ là tên ngẫu nhiên không có @)
      if (!seenEmails.has(core)) {
        uniqueParts.push(p);
        // Nếu chuỗi chứa @, đánh dấu core vào seenEmails để loại trừ các chuỗi khác trùng ruột
        if (core.includes("@")) {
          seenEmails.add(core);
          // Thử đánh dấu cả tên gốc vừa tìm để loại Name ra (Vd: Name <email@...>)
          const nameMatch = p.match(/^"?[^"]+"?\s+</) || p.match(/^[^<]+\s+</);
          if (nameMatch) {
            const potentialName = nameMatch[0].replace(/[<"\s]+/g, '').trim().toLowerCase();
            if (potentialName) seenEmails.add(potentialName);
          }
        } else {
          // Trường hợp không có @, nếu core (chính là tên) chưa có trong seenEmails thì giữ
          seenEmails.add(core); 
        }
      }
    }
    
    setEditParticipants(uniqueParts);
    setEditNote(action.payload?.note || "");
    setEditWeatherDependent(action.payload?.weather_dependent || false);
  };

  const handleSendModified = () => {
    if (editingIndex === null) return;
    onApprove(id, editingIndex, { 
      reply_body: editBody, 
      participants: editParticipants,
      note: editNote,
      weather_dependent: editWeatherDependent
    });
  };

  return (
    <div className={`proposal-card proposal-card--${source}`}>

      {/* Header */}
      <div className="proposal-card__header">
        <span className="proposal-card__badge">{badge}</span>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ConfidenceBadge confidence={proposal.confidence} />
          <button className="proposal-card__close" onClick={() => onDismiss(id)} title="Bỏ qua">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Title + sender */}
      <h3 className="proposal-card__title">{title}</h3>
      {fromLine && (
        <p className="proposal-card__meta">
          <Mail size={12} /> {fromLine}
        </p>
      )}
      {subtitle && <p className="proposal-card__summary">{subtitle}</p>}

      {/* Weather details */}
      {isWeatherSystem && proposal.weather_details && (
        <div style={{
          padding: "10px 12px",
          background: "rgba(245, 158, 11, 0.08)",
          borderRadius: "8px",
          border: "1px solid rgba(245, 158, 11, 0.25)",
          display: "flex",
          alignItems: "flex-start",
          gap: "8px",
          marginTop: "4px",
        }}>
          <CloudRain size={16} style={{ color: "#f59e0b", marginTop: "1px", flexShrink: 0 }} />
          <span style={{ fontSize: "12px", color: "#fcd34d", lineHeight: 1.5 }}>
            {proposal.weather_details}
          </span>
        </div>
      )}

      {/* Preview (legacy news agent body or email snippet) */}
      {!isEmailSecretary && !isWeatherSystem && proposal.payload?.body && (
        <div className="proposal-card__body-preview">
          {proposal.payload.body.substring(0, 160)}
          {proposal.payload.body.length > 160 ? "…" : ""}
        </div>
      )}

      {/* Dynamic action buttons OR Edit Form */}
      {editingIndex !== null && status === "pending" ? (
        <div style={{ marginTop: "12px", padding: "12px", background: "rgba(0,0,0,0.2)", borderRadius: "8px", border: "1px solid #444" }}>
          
          <h4 style={{ fontSize: "14px", margin: "0 0 10px 0", color: "#e2e8f0" }}>
            {actions[editingIndex]?.action_type === "cancel_event"
              ? "⛈️ Huỷ lịch hẹn & gửi email thông báo"
              : actions[editingIndex]?.action_type === "create_event"
              ? "Xác nhận Lịch & Tùy chỉnh Email"
              : "Chỉnh sửa phản hồi trước khi gửi"}
          </h4>

          {actions[editingIndex]?.action_type === "create_event" && (
            <div style={{ padding: "12px", background: "rgba(66, 133, 244, 0.1)", borderRadius: "6px", marginBottom: "12px", display: "flex", flexDirection: "column", gap: "10px", border: "1px solid rgba(66, 133, 244, 0.3)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Calendar size={16} color="#60a5fa" />
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#60a5fa" }}>Lưu Cuộc Hẹn Nội Bộ</span>
              </div>
              <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
                <div><strong style={{ opacity: 0.8 }}>Tiêu đề:</strong> {actions[editingIndex].payload?.title || proposal.email_subject}</div>
                <div><strong style={{ opacity: 0.8 }}>Thời gian:</strong> {actions[editingIndex].payload?.proposed_time ? new Date(actions[editingIndex].payload.proposed_time!).toLocaleString("vi-VN") : "Chưa rõ thời gian cụ thể"}</div>
              </div>

              {/* Note / Tóm tắt */}
              <div style={{ marginTop: "8px" }}>
                <label style={{ display: "block", fontSize: "12px", marginBottom: "6px", color: "#94a3b8" }}>Ghi chú công việc / Địa điểm:</label>
                <textarea
                  value={editNote}
                  onChange={(e) => setEditNote(e.target.value)}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", color: "white", fontSize: "13px", resize: "none" }}
                  rows={2}
                  placeholder="Tham luận dự án..."
                />
              </div>

              {/* Weather Conditional */}
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "#e2e8f0", marginTop: "4px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={editWeatherDependent}
                  onChange={(e) => setEditWeatherDependent(e.target.checked)}
                  style={{ width: "16px", height: "16px", cursor: "pointer" }}
                />
                Lịch trình ngoài trời / Có thể bị ảnh hưởng bởi thời tiết
              </label>
            </div>
          )}

          <div style={{ marginBottom: "12px" }}>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "6px", color: "#94a3b8" }}>
              {actions[editingIndex]?.action_type === "create_event" ? "Đồng gửi Email phản hồi tới người nhận:" : "Người nhận:"}
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
              {editParticipants.map((p, i) => (
                <span key={i} style={{ background: "#3b82f6", padding: "2px 8px", borderRadius: "12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                  {p}
                  <button onClick={() => setEditParticipants(prev => prev.filter((_, idx) => idx !== i))} style={{ background: "none", border: "none", color: "white", cursor: "pointer", padding: 0 }} title="Xóa">
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <input 
                type="email" 
                value={newParticipant} 
                onChange={(e) => setNewParticipant(e.target.value)}
                placeholder="Thêm email người nhận..."
                style={{ flex: 1, padding: "6px 10px", borderRadius: "6px", border: "1px solid #555", background: "#1e1e1e", color: "white", fontSize: "13px" }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newParticipant.trim()) {
                    e.preventDefault();
                    if (!editParticipants.includes(newParticipant.trim())) {
                      setEditParticipants(prev => [...prev, newParticipant.trim()]);
                    }
                    setNewParticipant("");
                  }
                }}
              />
              <button 
                onClick={() => {
                  if (newParticipant.trim() && !editParticipants.includes(newParticipant.trim())) {
                    setEditParticipants(prev => [...prev, newParticipant.trim()]);
                    setNewParticipant("");
                  }
                }}
                style={{ padding: "6px 12px", background: "#475569", color: "white", border: "none", borderRadius: "6px", cursor: "pointer" }}
                title="Thêm"
              >
                +
              </button>
            </div>
          </div>

          <div style={{ marginBottom: "12px" }}>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "6px", color: "#94a3b8" }}>Nội dung email:</label>
            <textarea
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              style={{ width: "100%", minHeight: "100px", padding: "10px", borderRadius: "6px", border: "1px solid #555", background: "#1e1e1e", color: "white", fontSize: "13px", resize: "vertical", fontFamily: "inherit" }}
            />
          </div>

          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            <button onClick={() => setEditingIndex(null)} style={{ padding: "6px 14px", background: "transparent", border: "1px solid #555", color: "#cbd5e1", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>
              Hủy
            </button>
            <button
              onClick={handleSendModified}
              style={{
                padding: "6px 14px",
                background: actions[editingIndex]?.action_type === "cancel_event" ? "#dc2626" : "#2563eb",
                border: "none",
                color: "white",
                borderRadius: "6px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "13px",
                fontWeight: 500,
              }}
            >
              <Send size={14} />
              {actions[editingIndex]?.action_type === "cancel_event"
                ? "Huỷ lịch & Gửi thông báo"
                : actions[editingIndex]?.action_type === "create_event"
                ? "Gửi Mail & Đồng bộ DB"
                : "Gửi ngay"}
            </button>
          </div>
        </div>
      ) : (
        <div className="proposal-card__actions">
          {status === "pending" && actions.map((action, idx) => (
            <button
              key={idx}
              className={`proposal-btn proposal-btn--${action.action_type === "ignore" ? "dismiss" : "approve"}`}
              onClick={() => handleActionClick(idx, action)}
              title={action.label}
            >
              <ActionIcon type={action.action_type} />
              {action.label}
            </button>
          ))}


        {status === "sending" && (
          <button className="proposal-btn proposal-btn--sending" disabled>
            <Clock size={15} className="animate-spin" />
            Đang xử lý...
          </button>
        )}

        {status === "sent" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
            <button className="proposal-btn proposal-btn--success" disabled>
              <CheckCircle2 size={15} />
              Hoàn thành! Đã lưu Database & Gửi Email.
            </button>
            {actions[proposal.activeActionIndex]?.action_type === "create_event" && (
              <span style={{ fontSize: "12px", color: "#60a5fa", textAlign: "center" }}>
                (Sự kiện đã được đồng bộ vào Tab "Lịch hẹn")
              </span>
            )}
          </div>
        )}

        {status === "error" && (
          <div className="proposal-error">
            <AlertCircle size={14} />
            {error || "Lỗi khi thực thi"}
            <button
              className="proposal-btn proposal-btn--approve"
              style={{ marginLeft: "8px", padding: "2px 10px" }}
              onClick={() => setEditingIndex(proposal.activeActionIndex)}
            >
              Thử lại / Sửa
            </button>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
