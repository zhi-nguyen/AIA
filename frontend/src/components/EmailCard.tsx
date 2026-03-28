/**
 * EmailCard.tsx — AI Secretary Meeting Proposal Card
 * Renders dynamically based on suggested_actions[] from Phase 3 AI Secretary
 * and (legacy) news_agent proposals.
 */

"use client";

import { CheckCircle2, Clock, Send, X, AlertCircle, Calendar, Mail, Ban } from "lucide-react";
import type { Proposal, SuggestedAction } from "@/hooks/useProposals";

interface ProposalCardProps {
  proposal: Proposal;
  onApprove: (id: string, actionIndex?: number) => void;
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

      {/* Dynamic action buttons */}
      <div className="proposal-card__actions">

        {status === "pending" && actions.map((action, idx) => (
          <button
            key={idx}
            className={`proposal-btn proposal-btn--${action.action_type === "ignore" ? "dismiss" : "approve"}`}
            onClick={() => onApprove(id, idx)}
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
          <button className="proposal-btn proposal-btn--success" disabled>
            <CheckCircle2 size={15} />
            Hoàn thành!
          </button>
        )}

        {status === "error" && (
          <div className="proposal-error">
            <AlertCircle size={14} />
            {error || "Lỗi khi thực thi"}
            <button
              className="proposal-btn proposal-btn--approve"
              style={{ marginLeft: "8px", padding: "2px 10px" }}
              onClick={() => onApprove(id, proposal.activeActionIndex)}
            >
              Thử lại
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
