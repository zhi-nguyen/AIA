/**
 * ProposalSidebar.tsx - Sidebar hiển thị đề xuất
 * Slide-in panel phong cách thống nhất với Weather & Calendar
 */

"use client";

import { Bell, X } from "lucide-react";
import ProposalCard from "@/components/EmailCard";
import type { Proposal } from "@/hooks/useProposals";

interface ProposalSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  proposals: Proposal[];
  onApprove: (id: string) => void;
  onDismiss: (id: string) => void;
}

export default function ProposalSidebar({
  isOpen,
  onClose,
  proposals,
  onApprove,
  onDismiss,
}: ProposalSidebarProps) {
  return (
    <div
      className={`weather-sidebar-overlay ${isOpen ? "weather-sidebar-overlay--open" : ""}`}
      onClick={onClose}
    >
      <div
        className={`weather-sidebar ${isOpen ? "weather-sidebar--open" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="weather-sidebar__header">
          <div className="weather-sidebar__header-left">
            <Bell size={20} style={{ color: "var(--warning)" }} />
            <h3 className="weather-sidebar__title">Đề xuất</h3>
            {proposals.length > 0 && (
              <span className="proposal-sidebar__count">{proposals.length}</span>
            )}
          </div>
          <button className="weather-sidebar__close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="weather-sidebar__content">
          {proposals.length === 0 ? (
            <div className="weather-sidebar__placeholder">
              <Bell size={40} style={{ opacity: 0.5, marginBottom: "12px" }} />
              <p>Không có đề xuất nào đang chờ</p>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Đề xuất từ AI sẽ xuất hiện tại đây
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {proposals.map((proposal) => (
                <ProposalCard
                  key={proposal.id}
                  proposal={proposal}
                  onApprove={onApprove}
                  onDismiss={onDismiss}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
