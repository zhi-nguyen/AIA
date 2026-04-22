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
  const isHigh = pct >= 70;
  const isMed = pct >= 40;
  const colorClass = isHigh ? "text-emerald-600" : isMed ? "text-amber-500" : "text-slate-500";
  return (
    <span className={`${colorClass} text-[11px] font-bold tracking-tight whitespace-nowrap`}>
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
      const core = extractCoreEmail(p).trim();
      // Giữ lại nếu là email duy nhất, hoặc không phải email (chỉ là tên ngẫu nhiên không có @)
      if (!seenEmails.has(core)) {
        uniqueParts.push(p);
        // Nếu chuỗi chứa @, đánh dấu core vào seenEmails để loại trừ các chuỗi khác trùng ruột
        if (core.includes("@")) {
          seenEmails.add(core);
          const nameMatch = p.match(/^"?[^"]+"?\s+</) || p.match(/^[^<]+\s+</);
          if (nameMatch) {
            const potentialName = nameMatch[0].replace(/["<]/g, '').trim().toLowerCase();
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
    <div className={`bg-white border rounded-2xl shadow-sm p-4 overflow-hidden mb-3 border-slate-200 transition-all hover:shadow-md ${isWeatherSystem ? 'border-amber-200 bg-amber-50/30' : ''}`}>

      {/* Header */}
      <div className="flex justify-between items-center mb-3 pb-3 border-b border-slate-100">
        <span className={`text-[11px] font-bold px-2.5 py-1 ${isWeatherSystem ? 'bg-amber-100 text-amber-800' : isEmailSecretary ? 'bg-indigo-100 text-indigo-700' : 'bg-sky-100 text-sky-700'} rounded-lg whitespace-nowrap`}>
          {badge}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ConfidenceBadge confidence={proposal.confidence} />
          <button className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors" onClick={() => onDismiss(id)} title="Bỏ qua">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Title + sender */}
      <h3 className="text-sm font-semibold text-slate-800 leading-snug mb-1.5">{title}</h3>
      {fromLine && (
        <p className="text-[11px] font-medium text-slate-500 flex items-center gap-1.5 mb-2.5">
          <Mail size={12} className="text-slate-400" /> {fromLine}
        </p>
      )}
      {subtitle && <p className="text-xs text-slate-700 bg-slate-50/80 p-3 rounded-xl border border-slate-100/80 leading-relaxed mb-3">{subtitle}</p>}

      {/* Weather details */}
      {isWeatherSystem && proposal.weather_details && (
        <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-xl border border-amber-200/60 mb-3">
          <CloudRain size={16} className="text-amber-500 mt-0.5 shrink-0" />
          <span className="text-xs text-amber-700 leading-relaxed">
            {proposal.weather_details}
          </span>
        </div>
      )}

      {/* Preview (legacy news agent body or email snippet) */}
      {!isEmailSecretary && !isWeatherSystem && proposal.payload?.body && (
        <div className="text-xs italic text-slate-500 bg-slate-50/50 p-3 rounded-xl border border-slate-100 mb-3 line-clamp-3">
          {proposal.payload.body.substring(0, 160)}
          {proposal.payload.body.length > 160 ? "…" : ""}
        </div>
      )}

      {/* Offline Queue Expiry specific notice */}
      {actions.find(a => a.action_type === "ignore" && a.payload?.note) && (
        <div className="flex items-start gap-2 p-3 bg-red-50 rounded-xl border border-red-200/60 mb-3">
          <Ban size={16} className="text-red-500 mt-0.5 shrink-0" />
          <span className="text-xs text-red-700 leading-relaxed font-medium">
            {actions.find(a => a.action_type === "ignore" && a.payload?.note)?.payload?.note}
          </span>
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
            <button onClick={() => setEditingIndex(null)} className="px-3.5 py-1.5 bg-transparent border border-gray-500 text-gray-300 rounded-lg hover:bg-gray-800 transition-colors cursor-pointer text-[13px] font-medium">
              Hủy
            </button>
            <button
              onClick={handleSendModified}
              className={`px-3.5 py-1.5 text-white rounded-lg cursor-pointer flex items-center gap-1.5 text-[13px] font-semibold transition-colors shadow-sm ${actions[editingIndex]?.action_type === "cancel_event" ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}
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
        <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-slate-100">
          {status === "pending" && actions.map((action, idx) => {
            const isDismiss = action.action_type === "ignore";
            return (
              <button
                key={idx}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-colors shadow-none ${isDismiss ? "bg-slate-50 text-slate-600 hover:bg-red-50 hover:text-red-700 border border-slate-200 hover:border-red-200" : "bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200"}`}
                onClick={() => handleActionClick(idx, action)}
                title={action.label}
              >
                <ActionIcon type={action.action_type} />
                {action.label}
              </button>
            );
          })}
          
          {status === "pending" && !actions.some(a => a.action_type === "ignore") && (
            <button
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-colors shadow-none bg-slate-50 text-slate-600 hover:bg-red-50 hover:text-red-700 border border-slate-200 hover:border-red-200"
              onClick={() => onDismiss(id)}
              title="Bỏ qua đề xuất này"
            >
              <Ban size={15} /> Bỏ qua
            </button>
          )}


        {status === "sending" && (
          <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-slate-100 text-slate-500 border border-slate-200 cursor-wait w-full justify-center" disabled>
            <Clock size={15} className="animate-spin text-slate-400" />
            Đang xử lý...
          </button>
        )}

        {status === "sent" && (
          <div className="flex flex-col gap-2 w-full">
            <button className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 cursor-default" disabled>
              <CheckCircle2 size={16} />
              Hoàn thành! Đã lưu Database & Gửi Email.
            </button>
            {actions[proposal.activeActionIndex]?.action_type === "create_event" && (
              <span className="text-[11px] font-semibold text-emerald-600/80 text-center block">
                (Sự kiện đã được đồng bộ vào Lịch hệ thống)
              </span>
            )}
          </div>
        )}

        {status === "error" && (
          <div className="flex items-center justify-between gap-2 p-2 rounded-lg text-xs font-medium bg-red-50 text-red-700 border border-red-200 w-full">
            <div className="flex items-center gap-1.5 truncate">
              <AlertCircle size={14} className="shrink-0" />
              <span className="truncate">{error || "Lỗi khi thực thi"}</span>
            </div>
            <button
              className="px-2.5 py-1 bg-white border border-red-200 rounded-md text-red-700 hover:bg-red-100 transition-colors shrink-0 font-bold"
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
