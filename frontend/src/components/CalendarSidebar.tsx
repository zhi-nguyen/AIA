/**
 * CalendarSidebar.tsx - Sidebar hiển thị lịch hẹn
 * Slide-in panel phong cách giống WeatherSidebar
 */

"use client";

import { useEffect, useState } from "react";
import { getEvents } from "@/lib/api";
import { Calendar, Clock, CloudRain, Users, AlignLeft, X, RefreshCw } from "lucide-react";

interface CalendarSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CalendarSidebar({ isOpen, onClose }: CalendarSidebarProps) {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchEvents = async () => {
    try {
      setIsRefreshing(true);
      setError(null);
      const res = await getEvents();
      setEvents(res || []);
    } catch (err: any) {
      setError(err.message || "Lỗi kết nối");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchEvents();
    }
  }, [isOpen]);

  // Group events by date
  const groupedEvents: Record<string, any[]> = {};
  events.forEach((ev) => {
    const dateKey = ev.proposed_time
      ? new Date(ev.proposed_time).toLocaleDateString("vi-VN", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      : "Chưa xác định";
    if (!groupedEvents[dateKey]) groupedEvents[dateKey] = [];
    groupedEvents[dateKey].push(ev);
  });

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
            <Calendar size={20} style={{ color: "#60a5fa" }} />
            <h3 className="weather-sidebar__title">Lịch hẹn</h3>
            {events.length > 0 && (
              <span className="calendar-sidebar__count">{events.length}</span>
            )}
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              className="weather-sidebar__refresh"
              onClick={fetchEvents}
              disabled={isRefreshing}
              title="Tải lại"
            >
              <RefreshCw size={16} className={isRefreshing ? "weather-spin" : ""} />
            </button>
            <button className="weather-sidebar__close" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="weather-sidebar__content">
          {loading && !isRefreshing ? (
            <div className="weather-sidebar__placeholder">
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
              <p>Đang tải lịch hẹn...</p>
            </div>
          ) : error ? (
            <div className="weather-sidebar__placeholder">
              <p style={{ color: "var(--error)" }}>Lỗi: {error}</p>
            </div>
          ) : events.length === 0 ? (
            <div className="weather-sidebar__placeholder">
              <Calendar size={40} style={{ opacity: 0.5, marginBottom: "12px" }} />
              <p>Chưa có lịch hẹn nào</p>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Hãy nhờ AIA tạo lịch hẹn qua chat
              </span>
            </div>
          ) : (
            <>
              {Object.entries(groupedEvents).map(([dateLabel, dayEvents]) => (
                <div key={dateLabel} className="calendar-date-group">
                  <div className="calendar-date-group__label">{dateLabel}</div>
                  <div className="calendar-date-group__events">
                    {dayEvents.map((ev, idx) => (
                      <div
                        key={ev.id || idx}
                        className={`calendar-event-card ${ev.weather_dependent ? "calendar-event-card--weather" : ""}`}
                      >
                        {/* Time strip */}
                        <div className="calendar-event-card__time">
                          <Clock size={13} />
                          <span>
                            {ev.proposed_time
                              ? new Date(ev.proposed_time).toLocaleTimeString("vi-VN", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "—"}
                          </span>
                        </div>

                        {/* Title */}
                        <h4 className="calendar-event-card__title">
                          {ev.title || "Không có tiêu đề"}
                        </h4>

                        {/* Weather badge */}
                        {ev.weather_dependent && (
                          <div className="calendar-event-card__badge">
                            <CloudRain size={12} />
                            <span>Phụ thuộc thời tiết</span>
                          </div>
                        )}

                        {/* Participants */}
                        {ev.participants && ev.participants.length > 0 && (
                          <div className="calendar-event-card__meta">
                            <Users size={13} />
                            <span>{ev.participants.join(", ")}</span>
                          </div>
                        )}

                        {/* Note */}
                        {ev.note && (
                          <div className="calendar-event-card__note">
                            <AlignLeft size={13} />
                            <span>{ev.note}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
