import { useState, useCallback, useEffect } from "react";
import { executeProposal } from "@/lib/api";

export type ProposalStatus = "pending" | "sending" | "sent" | "error";

export interface ProposalPayload {
  subject: string;
  body: string;
  recipients: string[];
}

export interface Proposal {
  id: string;
  title: string;
  summary: string;
  payload: ProposalPayload;
  status: ProposalStatus;
  error?: string;
  timestamp: number;
}

export function useProposals() {
  const [proposals, setProposals] = useState<Proposal[]>([]);

  // Lắng nghe window event "proposal_received" từ useChat
  useEffect(() => {
    const handleNewProposal = (e: Event) => {
      const customEvent = e as CustomEvent;
      const data = customEvent.detail;
      
      const newProposal: Proposal = {
        id: `prop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        title: data.title || "Đề xuất mới từ AIA",
        summary: data.summary || "Tôi có một đề xuất dựa trên sở thích của bạn.",
        payload: {
          subject: data.payload?.subject || "",
          body: data.payload?.body || "",
          recipients: data.payload?.recipients || [],
        },
        status: "pending",
        timestamp: Date.now(),
      };

      setProposals(prev => [...prev, newProposal]);
    };

    window.addEventListener("proposal_received", handleNewProposal);
    return () => {
      window.removeEventListener("proposal_received", handleNewProposal);
    };
  }, []);

  const dismissProposal = useCallback((id: string) => {
    setProposals(prev => prev.filter(p => p.id !== id));
  }, []);

  const approveProposal = useCallback(async (id: string) => {
    const proposal = proposals.find(p => p.id === id);
    if (!proposal || proposal.status !== "pending") return;

    // Cập nhật state -> sending
    setProposals(prev => 
      prev.map(p => p.id === id ? { ...p, status: "sending", error: undefined } : p)
    );

    try {
      await executeProposal(proposal.payload);
      
      // Thành công
      setProposals(prev => 
        prev.map(p => p.id === id ? { ...p, status: "sent" } : p)
      );

      // Tự động ẩn sau 3 giây nếu thành công
      setTimeout(() => {
        dismissProposal(id);
      }, 3000);

    } catch (err: any) {
      // Thất bại
      setProposals(prev => 
        prev.map(p => p.id === id ? { ...p, status: "error", error: err.message || "Lỗi giao tác" } : p)
      );
    }
  }, [proposals, dismissProposal]);

  return {
    proposals,
    approveProposal,
    dismissProposal
  };
}
