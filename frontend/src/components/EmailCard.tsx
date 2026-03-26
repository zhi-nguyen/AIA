"use client";

import { CheckCircle2, Clock, Send, X, AlertCircle } from "lucide-react";
import type { Proposal } from "@/hooks/useProposals";

interface ProposalCardProps {
  proposal: Proposal;
  onApprove: (id: string) => void;
  onDismiss: (id: string) => void;
}

export default function ProposalCard({ proposal, onApprove, onDismiss }: ProposalCardProps) {
  const { id, title, summary, payload, status, error, timestamp } = proposal;

  return (
    <div className="proposal-card">
      <div className="proposal-card__header">
        <span className="proposal-card__badge">Đề xuất tự động</span>
        <button 
          className="proposal-card__close"
          onClick={() => onDismiss(id)}
          title="Bỏ qua"
        >
          <X size={16} />
        </button>
      </div>

      <h3 className="proposal-card__title">{title}</h3>
      <p className="proposal-card__summary">{summary}</p>
      
      <div className="proposal-card__details">
        <div className="proposal-card__field">
          <strong>Tiêu đề:</strong> {payload.subject}
        </div>
        <div className="proposal-card__field">
          <strong>Người nhận:</strong> {payload.recipients.join(", ")}
        </div>
        <div className="proposal-card__body-preview">
          {payload.body.substring(0, 150)}{payload.body.length > 150 ? "..." : ""}
        </div>
      </div>

      <div className="proposal-card__actions">
        {status === "pending" && (
          <button 
            className="proposal-btn proposal-btn--approve"
            onClick={() => onApprove(id)}
          >
            <Send size={16} />
            Duyệt & Gửi Ngay
          </button>
        )}
        
        {status === "sending" && (
          <button className="proposal-btn proposal-btn--sending" disabled>
            <Clock size={16} className="animate-spin" />
            Đang gửi...
          </button>
        )}
        
        {status === "sent" && (
          <button className="proposal-btn proposal-btn--success" disabled>
            <CheckCircle2 size={16} />
            Đã gửi thành công
          </button>
        )}

        {status === "error" && (
          <div className="proposal-error">
            <AlertCircle size={14} />
            {error || "Lỗi khi gửi email"}
          </div>
        )}
      </div>
    </div>
  );
}
