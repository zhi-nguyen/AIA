/**
 * useProposals.ts - Hook quản lý AI Secretary proposals
 * Hỗ trợ cả format NEW_PROPOSAL (Phase 3 - meeting intent)
 * và new_proposal cũ (Phase 7 - news-based proposals).
 */

"use client";

import { useState, useCallback, useEffect } from "react";
import { executeProposal } from "@/lib/api";

export type ProposalStatus = "pending" | "sending" | "sent" | "error";
export type ActionType = "create_event" | "reply_email" | "ignore";

/** Payload cho một suggested action từ AI Secretary */
export interface SuggestedAction {
  action_type: ActionType;
  label: string;
  payload: {
    title?: string | null;
    participants?: string[];
    proposed_time?: string | null;
    reply_body?: string | null;
  };
}

/** Proposal chuẩn cho mọi loại card */
export interface Proposal {
  id: string;
  source: "email_secretary" | "news_agent";
  // Email secretary fields
  gmail_id?: string;
  email_subject?: string;
  email_from?: string;
  is_invitation?: boolean;
  confidence?: number;
  intent?: string;
  suggested_actions?: SuggestedAction[];
  // News agent (legacy) fields
  title?: string;
  summary?: string;
  payload?: {
    subject: string;
    body: string;
    recipients: string[];
  };
  // UX state
  status: ProposalStatus;
  activeActionIndex: number; // index trong suggested_actions đang được thực thi
  error?: string;
  timestamp: number;
}

/** Mapping action sang execute-proposal payload */
function buildExecutePayload(action: SuggestedAction, proposal: Proposal) {
  if (action.action_type === "create_event" || action.action_type === "reply_email") {
    return {
      subject: action.payload.title || proposal.email_subject || "",
      body: action.payload.reply_body || "",
      recipients: action.payload.participants ?? [],
      event_id: undefined as string | undefined,
      proposed_time: action.payload.proposed_time ?? undefined,
    };
  }
  // Fallback cho news agent legacy format
  return {
    subject: proposal.payload?.subject || "",
    body: proposal.payload?.body || "",
    recipients: proposal.payload?.recipients || [],
  };
}

export function useProposals() {
  const [proposals, setProposals] = useState<Proposal[]>([]);

  useEffect(() => {
    const handleNewProposal = (e: Event) => {
      const { detail } = e as CustomEvent;
      let newProposal: Proposal;

      if (detail.type === "NEW_PROPOSAL" && detail.source === "email_secretary") {
        // Phase 3: AI Secretary format
        const d = detail.data;
        newProposal = {
          id: `prop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          source: "email_secretary",
          gmail_id: d.gmail_id,
          email_subject: d.email_subject,
          email_from: d.email_from,
          is_invitation: d.is_invitation,
          confidence: d.confidence,
          intent: d.intent,
          suggested_actions: d.suggested_actions ?? [],
          status: "pending",
          activeActionIndex: 0,
          timestamp: Date.now(),
        };
      } else {
        // Legacy: news_agent format (new_proposal event from useChat)
        const d = detail;
        newProposal = {
          id: `prop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          source: "news_agent",
          title: d.title || "Đề xuất mới từ AIA",
          summary: d.summary || "",
          payload: {
            subject: d.payload?.subject || "",
            body: d.payload?.body || "",
            recipients: d.payload?.suggested_recipients || d.payload?.recipients || [],
          },
          status: "pending",
          activeActionIndex: 0,
          timestamp: Date.now(),
        };
      }

      setProposals((prev) => [...prev, newProposal]);
    };

    window.addEventListener("proposal_received", handleNewProposal);
    return () => window.removeEventListener("proposal_received", handleNewProposal);
  }, []);

  const dismissProposal = useCallback((id: string) => {
    setProposals((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const approveProposal = useCallback(
    async (id: string, actionIndex = 0) => {
      const proposal = proposals.find((p) => p.id === id);
      if (!proposal || proposal.status !== "pending") return;

      setProposals((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, status: "sending", activeActionIndex: actionIndex, error: undefined } : p
        )
      );

      try {
        let execPayload: Parameters<typeof executeProposal>[0];

        if (proposal.source === "email_secretary" && proposal.suggested_actions?.length) {
          const action = proposal.suggested_actions[actionIndex];
          if (action.action_type === "ignore") {
            // "Bỏ qua" — just dismiss without API call
            setProposals((prev) => prev.filter((p) => p.id !== id));
            return;
          }
          execPayload = buildExecutePayload(action, proposal);
        } else {
          execPayload = {
            subject: proposal.payload?.subject || "",
            body: proposal.payload?.body || "",
            recipients: proposal.payload?.recipients || [],
          };
        }

        await executeProposal(execPayload);

        setProposals((prev) =>
          prev.map((p) => (p.id === id ? { ...p, status: "sent" } : p))
        );
        setTimeout(() => dismissProposal(id), 3000);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Lỗi giao tác";
        setProposals((prev) =>
          prev.map((p) => (p.id === id ? { ...p, status: "error", error: message } : p))
        );
      }
    },
    [proposals, dismissProposal]
  );

  return { proposals, approveProposal, dismissProposal };
}
