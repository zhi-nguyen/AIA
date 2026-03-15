/**
 * NewsCard.tsx - Component hiển thị thẻ tin tức (Phase 4)
 * Placeholder cho Phase 4
 */

"use client";

interface NewsCardProps {
  title: string;
  source: string;
  summary: string;
  url: string;
}

export default function NewsCard({ title, source, summary, url }: NewsCardProps) {
  return (
    <div className="news-card">
      <span className="news-card__source">📰 {source}</span>
      <h3 className="news-card__title">{title}</h3>
      <p className="news-card__summary">{summary}</p>
      <a href={url} target="_blank" rel="noopener noreferrer" className="news-card__link">
        Đọc thêm →
      </a>
    </div>
  );
}
