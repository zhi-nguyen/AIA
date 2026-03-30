/**
 * EmailCard.tsx — AI Secretary Meeting Proposal Card
 * Renders dynamically based on suggested_actions[] from Phase 3 AI Secretary
 * and (legacy) news_agent proposals.
 */

"use client";

import { useState } from "react";
import { CheckCircle2, Clock, Send, X, AlertCircle, Calendar, Mail, Ban, ExternalLink } from "lucide-react";
import type { Proposal, SuggestedAction } from "@/hooks/useProposals";

interface ProposalCardProps {
  proposal: Proposal;
  onApprove: (id: string, actionIndex?: number, modifiedPayload?: { reply_body?: string; participants?: string[] }) => void;
  onDismiss: (id: string) => void;
}

/** Map action_type → icon */
function ActionIcon({ type }: { type: SuggestedAction["action_type"] }) {
  switch (type) {
    case "create_event": return <Calendar size={15} />;
    case "reply_email":  return <Mail size={15} />;
    default:             return <Ban size={15} />;
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

function buildGoogleCalendarUrl(action: SuggestedAction, proposal: Proposal): string {
  const p = action.payload;
  const title = p.title || proposal.email_subject || "Lịch hẹn (Đề xuất)";
  const details = `Đề xuất tạo lịch tự động từ AIA.\n\nEmail gốc: ${proposal.email_subject}\nNgười gửi: ${proposal.email_from}\n\nNội dung AI dự kiến trả lời:\n${p.reply_body || ""}`;
  const add = (p.participants || []).join(",");

  let dates = "";
  if (p.proposed_time) {
    try {
      const start = new Date(p.proposed_time);
      const end = new Date(start.getTime() + 60 * 60 * 1000); // 1 hour
      const fmt = (d: Date) => d.toISOString().replace(/-|:|\.\d\d\d/g, "");
      dates = `${fmt(start)}/${fmt(end)}`;
    } catch (e) {
      console.error(e);
    }
  }

  const params = new URLSearchParams();
  params.set("action", "TEMPLATE");
  params.set("text", title);
  if (dates) params.set("dates", dates);
  params.set("details", details);
  if (add) params.set("add", add);

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export default function ProposalCard({ proposal, onApprove, onDismiss }: ProposalCardProps) {
  const { id, source, status, error, timestamp } = proposal;
  const isEmailSecretary = source === "email_secretary";

  /* ── Header labels ── */
  const badge = isEmailSecretary ? "📅 Thư ký AI — Hẹn gặp" : "💡 Đề xuất tự động";

  /* ── Title & subtitle ── */
  const title = isEmailSecretary
    ? (proposal.email_subject || "Email không có tiêu đề")
    : (proposal.title || "Đề xuất mới từ AIA");
  const subtitle = isEmailSecretary
    ? (proposal.intent || "")
    : (proposal.summary || "");

  /* ── Body detail ── */
  const fromLine = isEmailSecretary ? proposal.email_from : null;

  /* ── Actions ── */
  const actions = isEmailSecretary
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

  const handleActionClick = (idx: number, action: SuggestedAction) => {
    if (action.action_type === "ignore") {
      onApprove(id, idx);
      return;
    }
    setEditingIndex(idx);
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
    setEditParticipants(action.payload?.participants || []);
  };

  const handleSendModified = () => {
    if (editingIndex === null) return;
    onApprove(id, editingIndex, { reply_body: editBody, participants: editParticipants });
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

      {/* Preview (legacy news agent body or email snippet) */}
      {!isEmailSecretary && proposal.payload?.body && (
        <div className="proposal-card__body-preview">
          {proposal.payload.body.substring(0, 160)}
          {proposal.payload.body.length > 160 ? "…" : ""}
        </div>
      )}

      {/* Dynamic action buttons OR Edit Form */}
      {editingIndex !== null && status === "pending" ? (
        <div style={{ marginTop: "12px", padding: "12px", background: "rgba(0,0,0,0.2)", borderRadius: "8px", border: "1px solid #444" }}>
          
          <h4 style={{ fontSize: "14px", margin: "0 0 10px 0", color: "#e2e8f0" }}>
            {actions[editingIndex]?.action_type === "create_event" ? "Xác nhận Lịch & Tùy chỉnh Email" : "Chỉnh sửa phản hồi trước khi gửi"}
          </h4>

          {actions[editingIndex]?.action_type === "create_event" && (
            <div style={{ padding: "12px", background: "rgba(66, 133, 244, 0.1)", borderRadius: "6px", marginBottom: "12px", display: "flex", flexDirection: "column", gap: "10px", border: "1px solid rgba(66, 133, 244, 0.3)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Calendar size={16} color="#60a5fa" />
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#60a5fa" }}>Lịch hẹn đã đề xuất</span>
              </div>
              <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
                <div><strong style={{ opacity: 0.8 }}>Tiêu đề:</strong> {actions[editingIndex].payload?.title || proposal.email_subject}</div>
                <div><strong style={{ opacity: 0.8 }}>Thời gian:</strong> {actions[editingIndex].payload?.proposed_time ? new Date(actions[editingIndex].payload.proposed_time!).toLocaleString("vi-VN") : "Chưa rõ thời gian cụ thể"}</div>
              </div>
              <a 
                href={buildGoogleCalendarUrl(actions[editingIndex], proposal)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex", alignItems: "center", gap: "6px", padding: "8px 12px", 
                  background: "#4285f4", color: "white", textDecoration: "none", borderRadius: "6px", 
                  fontSize: "13px", fontWeight: 500, width: "fit-content", marginTop: "4px"
                }}
              >
                <ExternalLink size={14} /> Mở trong Google Calendar
              </a>
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
            <button onClick={handleSendModified} style={{ padding: "6px 14px", background: "#2563eb", border: "none", color: "white", borderRadius: "6px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 500 }}>
              <Send size={14} /> {actions[editingIndex]?.action_type === "create_event" ? "Gửi Mail & Đồng bộ DB" : "Gửi ngay"}
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
              <a 
                href={buildGoogleCalendarUrl(actions[proposal.activeActionIndex], proposal)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "flex", justifyContent: "center", alignItems: "center", gap: "6px", padding: "8px", 
                  background: "#4285f4", color: "white", textDecoration: "none", borderRadius: "6px", 
                  fontSize: "13px", fontWeight: 500
                }}
              >
                <ExternalLink size={14} /> Mở Google Calendar
              </a>
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
