/**
 * EmailCard.tsx - Component hiển thị thẻ tóm tắt email (Phase 3)
 * Placeholder cho Phase 3
 */

"use client";

import { AlertCircle, AlertTriangle, ArrowDownCircle } from "lucide-react";

interface EmailCardProps {
  subject: string;
  from: string;
  summary: string;
  priority: "high" | "medium" | "low";
}

export default function EmailCard({ subject, from, summary, priority }: EmailCardProps) {
  const priorityIcon = {
    high: <AlertCircle className="text-red-500 w-4 h-4 inline" />,
    medium: <AlertTriangle className="text-yellow-500 w-4 h-4 inline" />,
    low: <ArrowDownCircle className="text-green-500 w-4 h-4 inline" />,
  };

  return (
    <div className="email-card">
      <div className="email-card__header">
        <span className="email-card__priority">{priorityIcon[priority]}</span>
        <span className="email-card__from">{from}</span>
      </div>
      <h3 className="email-card__subject">{subject}</h3>
      <p className="email-card__summary">{summary}</p>
    </div>
  );
}
