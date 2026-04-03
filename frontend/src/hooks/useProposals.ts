/**
 * useProposals.ts - Hook quản lý AI Secretary proposals
 * Hỗ trợ cả format NEW_PROPOSAL (Phase 3 - meeting intent)
 * và new_proposal cũ (Phase 7 - news-based proposals).
 */

"use client";

import { useState, useCallback, useEffect } from "react";
import { executeProposal, getProposals, deleteProposal } from "@/lib/api";

export type ProposalStatus = "pending" | "sending" | "sent" | "error";
export type ActionType = "create_event" | "reply_email" | "ignore" | "cancel_event";

/** Payload cho một suggested action từ AI Secretary */
export interface SuggestedAction {
  action_type: ActionType;
  label: string;
  payload: {
    title?: string | null;
    participants?: string[];
    proposed_time?: string | null;
    reply_body?: string | null;
    note?: string | null;
    weather_dependent?: boolean;
    // Weather cancel fields
    subject?: string;
    body?: string;
    recipients?: string[];
  };
}

/** Proposal chuẩn cho mọi loại card */
export interface Proposal {
  id: string;
  source: "email_secretary" | "news_agent" | "weather_system";
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
  // Weather system fields
  event_id?: string;
  event_title?: string;
  weather_reason?: string;
  weather_details?: string;
  // UX state
  status: ProposalStatus;
  activeActionIndex: number; // index trong suggested_actions đang được thực thi
  error?: string;
  timestamp: number;
}

/** Mapping action sang execute-proposal payload */
function buildExecutePayload(action: SuggestedAction, proposal: Proposal) {
  if (action.action_type === "cancel_event") {
    // Weather cancel: gửi email + huỷ event
    return {
      subject: action.payload.subject || `[Thông báo] Hoãn lịch hẹn: ${proposal.event_title || ""}`,
      body: action.payload.body || "",
      recipients: action.payload.recipients ?? [],
      cancel_event_id: proposal.event_id,
    };
  }
  if (action.action_type === "create_event" || action.action_type === "reply_email") {
    return {
      subject: action.payload.title || proposal.email_subject || "",
      body: action.payload.reply_body || "",
      recipients: action.payload.participants ?? [],
      event_id: undefined as string | undefined,
      proposed_time: action.payload.proposed_time ?? undefined,
      note: action.payload.note || undefined,
      weather_dependent: action.payload.weather_dependent || false,
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

  // Fetch from DB on mount
  useEffect(() => {
    getProposals()
      .then((data) => {
        if (data?.proposals) {
          const initialProposals = data.proposals.map((item: any) => {
            const d = item.payload;
            const isWeather = !!d.weather_reason;
            const source = isWeather ? "weather_system" : "email_secretary";
            
            return {
              id: item.id, // Use DB id
              source: source,
              // Email secretary fields
              gmail_id: d.gmail_id,
              email_subject: d.email_subject,
              email_from: d.email_from,
              is_invitation: d.is_invitation,
              confidence: d.confidence,
              intent: d.intent,
              // Weather system fields
              event_id: d.event_id,
              event_title: d.event_title,
              weather_reason: d.weather_reason,
              weather_details: d.weather_details,
              suggested_actions: d.suggested_actions ?? [],
              status: "pending",
              activeActionIndex: 0,
              timestamp: Date.now(),
            } as Proposal;
          });
          setProposals(initialProposals);
        }
      })
      .catch((err) => console.error("Failed to load persistent proposals:", err));
  }, []);

  useEffect(() => {
    const handleNewProposal = (e: Event) => {
      const { detail } = e as CustomEvent;
      let newProposal: Proposal;

      if (detail.type === "WEATHER_ALERT" && detail.source === "weather_system") {
        // Weather system alert
        const d = detail.data;
        newProposal = {
          id: d.db_id || `prop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          source: "weather_system",
          event_id: d.event_id,
          event_title: d.event_title,
          weather_reason: d.weather_reason,
          weather_details: d.weather_details,
          suggested_actions: d.suggested_actions ?? [],
          status: "pending",
          activeActionIndex: 0,
          timestamp: Date.now(),
        };
      } else if (detail.type === "NEW_PROPOSAL" && detail.source === "email_secretary") {
        // Phase 3: AI Secretary format
        const d = detail.data;
        newProposal = {
          id: d.db_id || `prop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
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

      setProposals((prev) => {
        // Tránh trùng lặp nếu WS gửi nhiều lần
        if (prev.some(p => p.id === newProposal.id)) return prev;
        return [...prev, newProposal];
      });
    };

    window.addEventListener("proposal_received", handleNewProposal);
    return () => window.removeEventListener("proposal_received", handleNewProposal);
  }, []);

  const dismissProposal = useCallback((id: string) => {
    setProposals((prev) => prev.filter((p) => p.id !== id));
    // Only call deleteAPI if it looks like a DB UUID (not prop_...)
    if (!id.startsWith("prop_")) {
      deleteProposal(id).catch((err) => console.error("Failed to delete proposal DB", err));
    }
  }, []);

  const approveProposal = useCallback(
    async (
      id: string,
      actionIndex = 0,
      modifiedPayload?: { reply_body?: string; participants?: string[]; note?: string; weather_dependent?: boolean }
    ) => {
      const proposal = proposals.find((p) => p.id === id);
      if (!proposal || proposal.status !== "pending") return;

      setProposals((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, status: "sending", activeActionIndex: actionIndex, error: undefined } : p
        )
      );

      try {
        let execPayload: Parameters<typeof executeProposal>[0];

        if ((proposal.source === "email_secretary" || proposal.source === "weather_system") && proposal.suggested_actions?.length) {
          const action = proposal.suggested_actions[actionIndex];
          if (action.action_type === "ignore") {
            // "Bỏ qua" — just dismiss
            dismissProposal(id);
            return;
          }
          execPayload = buildExecutePayload(action, proposal);
          if (modifiedPayload) {
            if (modifiedPayload.reply_body !== undefined) execPayload.body = modifiedPayload.reply_body;
            if (modifiedPayload.participants !== undefined) execPayload.recipients = modifiedPayload.participants;
            if (modifiedPayload.note !== undefined) execPayload.note = modifiedPayload.note;
            if (modifiedPayload.weather_dependent !== undefined) execPayload.weather_dependent = modifiedPayload.weather_dependent;
          }
        } else {
          execPayload = {
            subject: proposal.payload?.subject || "",
            body: modifiedPayload?.reply_body !== undefined ? modifiedPayload.reply_body : (proposal.payload?.body || ""),
            recipients: modifiedPayload?.participants !== undefined ? modifiedPayload.participants : (proposal.payload?.recipients || []),
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
