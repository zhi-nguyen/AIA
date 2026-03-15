/**
 * EmailCard.tsx - Component hiển thị thẻ tóm tắt email (Phase 3)
 * Placeholder cho Phase 3
 */

"use client";

interface EmailCardProps {
  subject: string;
  from: string;
  summary: string;
  priority: "high" | "medium" | "low";
}

export default function EmailCard({ subject, from, summary, priority }: EmailCardProps) {
  const priorityIcon = {
    high: "🔴",
    medium: "🟡",
    low: "🟢",
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
