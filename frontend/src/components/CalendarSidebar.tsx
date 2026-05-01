/**
 * CalendarSidebar.tsx - Sidebar hiển thị lịch hẹn
 * Slide-in panel phong cách giống WeatherSidebar
 */

"use client";

import { useEffect, useState } from "react";
import { getEvents, updateEvent, cancelEvent, completeEvent, createEvent } from "@/lib/api";
import { Calendar, Clock, CloudRain, Users, AlignLeft, X, RefreshCw, ChevronLeft, ChevronRight, Edit2, Trash2, Send, CheckCircle, Plus } from "lucide-react";

interface CalendarSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CalendarSidebar({ isOpen, onClose }: CalendarSidebarProps) {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Calendar States
  const today = new Date();
  const [currentMonth, setCurrentMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  // Edit / Cancel States
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [editFormData, setEditFormData] = useState<any>({});
  
  const [cancelingEventId, setCancelingEventId] = useState<string | null>(null);
  const [cancelReplyBody, setCancelReplyBody] = useState("");

  // Create Event State
  const [isCreatingEvent, setIsCreatingEvent] = useState(false);
  const [createFormData, setCreateFormData] = useState<any>({
    title: "",
    proposed_time: "",
    note: "",
    participants: "",
    weather_dependent: false
  });

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
      // Reset selected date to today when opening
      if (!selectedDate) setSelectedDate(new Date());
    }
  }, [isOpen]);

  // Handle Event Creation
  const handleCreateEvent = async () => {
    try {
      setIsRefreshing(true);
      const currentParticipants = typeof createFormData.participants === 'string' 
        ? createFormData.participants.split(',').map((p: string) => p.trim()).filter(Boolean)
        : createFormData.participants;

      await createEvent({
        title: createFormData.title || "Lịch hẹn mới",
        proposed_time: createFormData.proposed_time || new Date().toISOString(),
        note: createFormData.note,
        participants: currentParticipants,
        weather_dependent: createFormData.weather_dependent
      });
      setIsCreatingEvent(false);
      setCreateFormData({title: "", proposed_time: "", note: "", participants: "", weather_dependent: false});
      await fetchEvents();
    } catch (err: any) {
      alert("Lỗi tạo lịch: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Handle Event Saving
  const handleSaveEdit = async () => {
    if (!editingEventId) return;
    try {
      setIsRefreshing(true);
      
      // Convert participants single string back to array if needed
      const currentParticipants = typeof editFormData.participants === 'string' 
        ? editFormData.participants.split(',').map((p: string) => p.trim()).filter(Boolean)
        : editFormData.participants;

      await updateEvent(editingEventId, {
        title: editFormData.title,
        proposed_time: editFormData.proposed_time,
        note: editFormData.note,
        participants: currentParticipants,
        weather_dependent: editFormData.weather_dependent
      });
      setEditingEventId(null);
      await fetchEvents();
    } catch (err: any) {
      alert("Lỗi lưu thay đổi: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleConfirmCancel = async (ev: any) => {
    if (!cancelingEventId) return;
    try {
      setIsRefreshing(true);
      await cancelEvent(cancelingEventId, cancelReplyBody, ev.participants);
      setCancelingEventId(null);
      setCancelReplyBody("");
      await fetchEvents();
    } catch (err: any) {
      alert("Lỗi huỷ lịch: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCompleteEvent = async (ev: any) => {
    try {
      setIsRefreshing(true);
      await completeEvent(ev.id);
      await fetchEvents();
    } catch (err: any) {
      alert("Lỗi hoàn thành sự kiện: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Group events by YYYY-MM-DD
  const eventsByDateStr: Record<string, any[]> = {};
  events.forEach((ev) => {
    if (!ev.proposed_time) return;
    const d = new Date(ev.proposed_time);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    if (!eventsByDateStr[key]) eventsByDateStr[key] = [];
    eventsByDateStr[key].push(ev);
  });

  // Calendar logic
  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  const firstDayOfMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1).getDay(); // 0 (Sun) to 6 (Sat)
  const daysArray = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const paddingBefore = Array.from({ length: firstDayOfMonth === 0 ? 6 : firstDayOfMonth - 1 }, (_, i) => i); // Make Mon=0

  const moveMonth = (offset: number) => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + offset, 1));
  };

  const isSelectedDate = (d: number) => {
    if (!selectedDate) return false;
    return selectedDate.getDate() === d &&
           selectedDate.getMonth() === currentMonth.getMonth() &&
           selectedDate.getFullYear() === currentMonth.getFullYear();
  };

  const hasPendingEventOnDate = (d: number) => {
    const key = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayEvents = eventsByDateStr[key];
    if (!dayEvents) return false;
    return dayEvents.some(e => e.status !== 'completed');
  };

  // Filtered Events
  let visibleEvents = events;
  if (selectedDate) {
    const key = `${selectedDate.getFullYear()}-${String(selectedDate.getMonth() + 1).padStart(2, '0')}-${String(selectedDate.getDate()).padStart(2, '0')}`;
    visibleEvents = eventsByDateStr[key] || [];
  }

  // Format datetime for input type="datetime-local" handler
  const toDateTimeLocalFormat = (isoStr: string) => {
    if (!isoStr) return "";
    const date = new Date(isoStr);
    const tzOffset = date.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(date.getTime() - tzOffset)).toISOString().slice(0, 16);
    return localISOTime;
  };

  if (!isOpen) return null;

  return (
    <div className="absolute top-0 right-0 h-full w-[420px] bg-slate-900 shadow-2xl border-l border-slate-700 z-30 flex flex-col panel-slide-in text-white text-sm">
      {/* Header */}
      <div className="flex justify-between items-center bg-slate-800 border-b border-slate-700 p-5 shrink-0">
        <h2 className="font-bold text-white flex items-center gap-2 text-lg">
          <Calendar size={20} className="text-blue-400" /> Lịch hẹn
          {events.length > 0 && <span className="ml-2 px-2.5 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-full">{events.length}</span>}
        </h2>
        <div className="flex gap-2 items-center">
          <button
            className="p-2 bg-blue-600/20 text-blue-400 hover:text-white hover:bg-blue-600/40 rounded-xl transition-colors border border-blue-500/30"
            onClick={() => setIsCreatingEvent(true)}
            title="Tạo lịch hẹn mới"
          >
            <Plus size={16} />
          </button>
          <button
            className="p-2 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 rounded-xl transition-colors border border-slate-700"
            onClick={fetchEvents}
            disabled={isRefreshing}
            title="Tải lại"
          >
            <RefreshCw size={16} className={isRefreshing ? "animate-spin" : ""} />
          </button>
          <button className="p-2 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 rounded-xl transition-colors border border-slate-700" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content */}
        <div className="weather-sidebar__content" style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
          
          {/* Calendar Grid Widget */}
          <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: "12px", border: "1px solid #333", padding: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <button onClick={() => moveMonth(-1)} style={{ background: "transparent", border: "none", color: "#ccc", cursor: "pointer" }}><ChevronLeft size={20}/></button>
              <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 600, color: "#e2e8f0" }}>
                Tháng {currentMonth.getMonth() + 1}, {currentMonth.getFullYear()}
              </h4>
              <button onClick={() => moveMonth(1)} style={{ background: "transparent", border: "none", color: "#ccc", cursor: "pointer" }}><ChevronRight size={20}/></button>
            </div>
            
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px", textAlign: "center", fontSize: "12px", color: "#94a3b8", marginBottom: "8px" }}>
              <div>Hai</div><div>Ba</div><div>Tư</div><div>Năm</div><div>Sáu</div><div>Bảy</div><div>CN</div>
            </div>
            
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px" }}>
              {paddingBefore.map(idx => <div key={`pad-${idx}`} />)}
              {daysArray.map(d => (
                <div 
                  key={d} 
                  onClick={() => setSelectedDate(new Date(currentMonth.getFullYear(), currentMonth.getMonth(), d))}
                  style={{ 
                    position: "relative",
                    aspectRatio: "1", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center",
                    fontSize: "13px",
                    borderRadius: "8px",
                    cursor: "pointer",
                    background: isSelectedDate(d) ? "#3b82f6" : "transparent",
                    color: isSelectedDate(d) ? "white" : "#cbd5e1",
                    transition: "all 0.2s"
                  }}
                  onMouseOver={(e) => !isSelectedDate(d) && (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                  onMouseOut={(e) => !isSelectedDate(d) && (e.currentTarget.style.background = "transparent")}
                >
                  {d}
                  {hasPendingEventOnDate(d) && (
                    <div style={{ position: "absolute", bottom: "4px", width: "4px", height: "4px", borderRadius: "50%", background: isSelectedDate(d) ? "white" : "#ef4444" }} />
                  )}
                </div>
              ))}
            </div>
            <div style={{ marginTop: "12px", display: "flex", justifyContent: "center" }}>
               {selectedDate && (
                 <button onClick={() => setSelectedDate(null)} style={{ background: "transparent", border: "none", color: "#60a5fa", fontSize: "12px", cursor: "pointer", textDecoration: "underline" }}>
                   Bỏ lọc, xem toàn bộ
                 </button>
               )}
            </div>
          </div>

          <hr style={{ borderColor: "#333", margin: "4px 0" }}/>

          {isCreatingEvent && (
            <div style={{ padding: "12px", background: "rgba(59, 130, 246, 0.1)", borderRadius: "8px", border: "1px solid rgba(59, 130, 246, 0.3)", marginBottom: "12px" }}>
              <h4 style={{ margin: "0 0 12px 0", color: "#60a5fa", fontSize: "14px", display: "flex", alignItems: "center", gap: "6px" }}>
                <Plus size={16} /> Tạo lịch hẹn mới
              </h4>
              <input 
                type="text" 
                placeholder="Tiêu đề lịch hẹn..."
                value={createFormData.title} 
                onChange={(e) => setCreateFormData({...createFormData, title: e.target.value})}
                style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "14px", fontWeight: "bold" }}
              />
              
              <input 
                type="datetime-local" 
                value={createFormData.proposed_time ? toDateTimeLocalFormat(createFormData.proposed_time) : ""} 
                onChange={(e) => setCreateFormData({...createFormData, proposed_time: e.target.value ? (new Date(e.target.value)).toISOString() : ""})}
                style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px" }}
              />
              
              <input 
                type="text" 
                placeholder="Thành viên tham dự (Cách nhau bởi dấu phẩy)"
                value={createFormData.participants} 
                onChange={(e) => setCreateFormData({...createFormData, participants: e.target.value})}
                style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px" }}
              />

              <textarea
                placeholder="Ghi chú công việc..."
                value={createFormData.note}
                onChange={(e) => setCreateFormData({...createFormData, note: e.target.value})}
                style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px", resize: "none" }}
                rows={2}
              />

              <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#cbd5e1", marginBottom: "12px", cursor: "pointer" }}>
                <input type="checkbox" checked={createFormData.weather_dependent} onChange={(e) => setCreateFormData({...createFormData, weather_dependent: e.target.checked})} />
                Ngoài trời / Bị ảnh hưởng bởi thời tiết
              </label>

              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                <button onClick={() => setIsCreatingEvent(false)} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "rgba(255,255,255,0.1)", color: "white", fontSize: "12px", cursor: "pointer" }}>Hủy</button>
                <button onClick={handleCreateEvent} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "#3b82f6", color: "white", fontSize: "12px", cursor: "pointer" }}>Tạo lịch</button>
              </div>
            </div>
          )}

          {loading && !isRefreshing ? (
            <div className="typing-indicator" style={{ alignSelf: "center" }}>
              <span /><span /><span />
            </div>
          ) : error ? (
            <p style={{ color: "var(--error)", textAlign: "center" }}>Lỗi: {error}</p>
          ) : visibleEvents.length === 0 ? (
            <div className="weather-sidebar__placeholder">
              <Calendar size={40} style={{ opacity: 0.5, marginBottom: "12px" }} />
              <p>{selectedDate ? "Không có lịch hẹn nào vào ngày này" : "Chưa có lịch hẹn nào"}</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", overflowY: "auto", paddingRight: "4px", paddingBottom: "20px" }}>
              {visibleEvents.map((ev, idx) => (
                <div key={ev.id || idx} className={`calendar-event-card ${ev.weather_dependent ? "calendar-event-card--weather" : ""}`} style={{ position: "relative", opacity: ev.status === 'completed' ? 0.6 : 1 }}>
                  
                  {/* Cancel Modal/Box within the card */}
                  {cancelingEventId === ev.id ? (
                     <div style={{ padding: "12px", background: "rgba(239, 68, 68, 0.1)", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
                        <h4 style={{ margin: "0 0 8px 0", color: "#fca5a5", fontSize: "13px" }}>Bạn chuẩn bị huỷ lịch: {ev.title}</h4>
                        <p style={{ fontSize: "12px", color: "#cbd5e1", marginBottom: "8px" }}>
                          Có muốn tự động báo huỷ cho người tham gia? Hãy điền lý do bên dưới (hoặc bỏ trống nếu k gửi).
                        </p>
                        <textarea
                          placeholder="Lý do huỷ hẹn..."
                          value={cancelReplyBody}
                          onChange={(e) => setCancelReplyBody(e.target.value)}
                          style={{ width: "100%", padding: "8px", borderRadius: "6px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", color: "white", fontSize: "13px", resize: "none", marginBottom: "8px" }}
                          rows={3}
                        />
                        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                          <button onClick={() => setCancelingEventId(null)} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "rgba(255,255,255,0.1)", color: "white", fontSize: "12px", cursor: "pointer" }}>Đóng</button>
                          <button onClick={() => handleConfirmCancel(ev)} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "#ef4444", color: "white", fontSize: "12px", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px" }}>
                            {cancelReplyBody.trim() ? <><Send size={12}/> Huỷ & Báo</> : "Huỷ Lịch"}
                          </button>
                        </div>
                     </div>
                  ) : editingEventId === ev.id ? (
                     <div style={{ padding: "12px", background: "rgba(255, 255, 255, 0.05)", borderRadius: "8px" }}>
                       <input 
                         type="text" 
                         value={editFormData.title} 
                         onChange={(e) => setEditFormData({...editFormData, title: e.target.value})}
                         style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "14px", fontWeight: "bold" }}
                       />
                       
                       <input 
                         type="datetime-local" 
                         value={toDateTimeLocalFormat(editFormData.proposed_time)} 
                         onChange={(e) => setEditFormData({...editFormData, proposed_time: (new Date(e.target.value)).toISOString()})}
                         style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px" }}
                       />
                       
                       <input 
                         type="text" 
                         placeholder="Thành viên tham dự (Cách nhau bởi dấu phẩy)"
                         value={typeof editFormData.participants === 'string' ? editFormData.participants : (editFormData.participants||[]).join(', ')} 
                         onChange={(e) => setEditFormData({...editFormData, participants: e.target.value})}
                         style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px" }}
                       />

                       <textarea
                         placeholder="Ghi chú công việc..."
                         value={editFormData.note || ""}
                         onChange={(e) => setEditFormData({...editFormData, note: e.target.value})}
                         style={{ width: "100%", padding: "6px 8px", background: "rgba(0,0,0,0.3)", border: "1px solid #555", borderRadius: "4px", color: "white", marginBottom: "8px", fontSize: "13px", resize: "none" }}
                         rows={2}
                       />

                       <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#cbd5e1", marginBottom: "12px", cursor: "pointer" }}>
                         <input type="checkbox" checked={editFormData.weather_dependent} onChange={(e) => setEditFormData({...editFormData, weather_dependent: e.target.checked})} />
                         Ngoài trời / Bị ảnh hưởng bởi thời tiết
                       </label>

                       <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                          <button onClick={() => setEditingEventId(null)} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "rgba(255,255,255,0.1)", color: "white", fontSize: "12px", cursor: "pointer" }}>Hủy</button>
                          <button onClick={handleSaveEdit} style={{ padding: "6px 12px", borderRadius: "6px", border: "none", background: "#3b82f6", color: "white", fontSize: "12px", cursor: "pointer" }}>Lưu lại</button>
                       </div>
                     </div>
                  ) : (
                    <>
                      <div style={{ position: "absolute", top: "12px", right: "12px", display: "flex", gap: "6px" }}>
                        {ev.status !== 'completed' && (
                          <button onClick={() => handleCompleteEvent(ev)} style={{ background: "rgba(34, 197, 94, 0.2)", border: "none", color: "#4ade80", padding: "4px", borderRadius: "4px", cursor: "pointer" }} title="Hoàn thành"><CheckCircle size={14} /></button>
                        )}
                        <button onClick={() => {setEditingEventId(ev.id); setEditFormData({...ev});}} style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#cbd5e1", padding: "4px", borderRadius: "4px", cursor: "pointer" }} title="Sửa"><Edit2 size={14} /></button>
                        <button onClick={() => {setCancelingEventId(ev.id); setCancelReplyBody("");}} style={{ background: "rgba(239, 68, 68, 0.2)", border: "none", color: "#fca5a5", padding: "4px", borderRadius: "4px", cursor: "pointer" }} title="Xoá / Huỷ"><Trash2 size={14} /></button>
                      </div>

                      {/* Time strip */}
                      <div className="calendar-event-card__time">
                        <Clock size={13} />
                        <span>
                          {ev.proposed_time
                            ? new Date(ev.proposed_time).toLocaleString("vi-VN", {
                                hour: "2-digit",
                                minute: "2-digit",
                                day: "2-digit",
                                month: "2-digit"
                              })
                            : "—"}
                        </span>
                      </div>

                      {/* Title */}
                      <h4 className="calendar-event-card__title" style={{ paddingRight: "70px", textDecoration: ev.status === 'completed' ? "line-through" : "none" }}>
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
                          <span style={{ wordBreak: "break-all" }}>{ev.participants.join(", ")}</span>
                        </div>
                      )}

                      {/* Note */}
                      {ev.note && (
                        <div className="calendar-event-card__note">
                          <AlignLeft size={13} />
                          <span>{ev.note}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}
