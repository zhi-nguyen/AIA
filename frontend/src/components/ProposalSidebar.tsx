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
  onApprove: (id: string, actionIndex?: number, modifiedPayload?: any) => void;
  onDismiss: (id: string) => void;
}

export default function ProposalSidebar({
  isOpen,
  onClose,
  proposals,
  onApprove,
  onDismiss,
}: ProposalSidebarProps) {
  if (!isOpen) return null;

  return (
    <div className="absolute top-0 right-0 h-full w-[420px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col panel-slide-in">
      <div className="flex justify-between items-center bg-slate-50 border-b border-slate-100 p-5 shrink-0">
        <h2 className="font-bold text-slate-800 flex items-center gap-2 text-lg">
          <Bell className="w-5 h-5 text-indigo-500" /> Đề xuất
          {proposals.length > 0 && <span className="ml-2 px-2.5 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-bold rounded-full">{proposals.length}</span>}
        </h2>
        <button type="button" onClick={onClose} className="p-2 bg-white text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar bg-slate-50/50">
        {proposals.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <Bell className="w-12 h-12 mb-4 opacity-30 text-indigo-500" />
            <p className="text-sm font-semibold text-slate-500">Tuyệt vời, tất cả đã xong!</p>
            <span className="text-xs mt-1 text-slate-400 text-center px-4">AI sẽ thông báo tại đây khi có đề xuất công việc hoặc phát hiện lịch hẹn mới.</span>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
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
  );
}
