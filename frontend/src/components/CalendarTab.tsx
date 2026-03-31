"use client";

import { useEffect, useState } from "react";
import { getEvents } from "@/lib/api";
import { Calendar, Clock, CloudRain, Users, AlignLeft } from "lucide-react";

export default function CalendarTab() {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getEvents().then((res: any[]) => {
      if (mounted) {
        setEvents(res || []);
        setLoading(false);
      }
    }).catch((err: Error) => {
      if (mounted) {
        setError(err.message);
        setLoading(false);
      }
    });

    return () => { mounted = false; };
  }, []);

  if (loading) return <div style={{ padding: 20, color: '#94a3b8' }}>Đang tải lịch hẹn...</div>;
  if (error) return <div style={{ padding: 20, color: '#ef4444' }}>Lỗi: {error}</div>;

  if (events.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", padding: "40px" }}>
        <Calendar size={48} opacity={0.5} style={{ marginBottom: "16px" }} />
        <p>Bạn chưa có lịch hẹn nào sắp tới.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px", overflowY: "auto", height: "100%", flex: 1 }}>
      <h2 style={{ fontSize: "20px", fontWeight: "bold", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
        <Calendar size={20} color="#60a5fa" /> Lịch hẹn của tôi
      </h2>
      
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {events.map((ev, idx) => (
          <div key={ev.id || idx} style={{ 
            background: "rgba(30, 41, 59, 0.7)", 
            border: "1px solid rgba(255, 255, 255, 0.1)", 
            borderRadius: "12px", 
            padding: "16px",
            display: "flex", flexDirection: "column", gap: "8px",
            position: "relative"
          }}>
            {ev.weather_dependent && (
              <div title="Có thể bị ảnh hưởng bởi thời tiết" style={{ position: "absolute", top: "16px", right: "16px", color: "#60a5fa", background: "rgba(96, 165, 250, 0.1)", padding: "4px 8px", borderRadius: "8px", display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", fontWeight: "bold" }}>
                <CloudRain size={14} /> Có yếu tố thời tiết
              </div>
            )}
            <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#f8fafc", margin: 0, paddingRight: "150px" }}>{ev.title || "Không có tiêu đề"}</h3>
            
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#cbd5e1", fontSize: "13px" }}>
              <Clock size={14} color="#94a3b8" />
              <span>{ev.proposed_time ? new Date(ev.proposed_time).toLocaleString("vi-VN") : "Thời gian chưa xác định"}</span>
            </div>

            {ev.participants && ev.participants.length > 0 && (
              <div style={{ display: "flex", gap: "6px", color: "#cbd5e1", fontSize: "13px" }}>
                <Users size={14} color="#94a3b8" style={{ marginTop: "2px", flexShrink: 0 }} />
                <span>{ev.participants.join(", ")}</span>
              </div>
            )}

            {ev.note && (
              <div style={{ display: "flex", gap: "8px", color: "#94a3b8", fontSize: "13px", marginTop: "6px", background: "rgba(0,0,0,0.2)", padding: "10px", borderRadius: "8px", borderLeft: "3px solid #60a5fa" }}>
                <AlignLeft size={14} style={{ marginTop: "2px", flexShrink: 0, color: "#60a5fa" }} />
                <span>{ev.note}</span>
              </div>
            )}
            
          </div>
        ))}
      </div>
    </div>
  );
}
