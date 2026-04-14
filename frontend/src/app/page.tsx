"use client";

import React, { useState } from 'react';
import { 
  Settings, Mail, Calendar, Cloud, Newspaper, 
  Bell, Lightbulb, MessageSquare, Plus, X, 
  ToggleRight, ToggleLeft, Send, CheckCircle2, User, LayoutGrid, RotateCw, Hash
} from 'lucide-react';

// --- THÀNH PHẦN UI CƠ BẢN ---
const Card = ({ title, icon: Icon, children, className = "" }: { title: string, icon: any, children: React.ReactNode, className?: string }) => (
  <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col overflow-hidden ${className}`}>
    <div className="flex items-center gap-2 p-4 border-b border-slate-100 bg-slate-50/50">
      <Icon className="w-5 h-5 text-indigo-500" />
      <h3 className="font-semibold text-slate-800 tracking-tight">{title}</h3>
    </div>
    <div className="p-4 flex-1 overflow-y-auto custom-scrollbar">
      {children}
    </div>
  </div>
);

const Toggle = ({ active, onClick }: { active: boolean, onClick: () => void }) => (
  <button onClick={onClick} className="focus:outline-none transition-colors">
    {active ? (
      <ToggleRight className="w-8 h-8 text-indigo-500" />
    ) : (
      <ToggleLeft className="w-8 h-8 text-slate-300" />
    )}
  </button>
);

// --- MODAL CONFIG ---
const ConfigPanel = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => {
  if (!isOpen) return null;

  const [activeTab, setActiveTab] = useState('accounts');
  const [settings, setSettings] = useState({
    runWithWindows: true,
    closeOnExit: false,
    suggestWork: true,
    suggestLife: true
  });
  const [interestTags, setInterestTags] = useState<string[]>(['Công nghệ', 'React.js', 'Python', 'AI / LLM']);
  const [tagInput, setTagInput] = useState('');

  const toggleSetting = (key: keyof typeof settings) => setSettings(prev => ({ ...prev, [key]: !prev[key] }));

  const addTag = () => {
    const trimmed = tagInput.trim();
    if (trimmed && !interestTags.includes(trimmed)) {
      setInterestTags(prev => [...prev, trimmed]);
      setTagInput('');
    }
  };

  const removeTag = (tag: string) => {
    setInterestTags(prev => prev.filter(t => t !== tag));
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
      <div className="bg-white w-full max-w-4xl rounded-3xl shadow-2xl overflow-hidden flex flex-col md:flex-row h-[85vh] md:h-[600px] animate-in fade-in zoom-in-95 duration-200">
        <div className="w-full md:w-64 bg-slate-50 border-r border-slate-100 p-6 flex flex-col gap-2 shrink-0">
          <h2 className="text-xl font-bold text-slate-800 mb-6 px-2 flex items-center gap-2">
            <Settings className="w-5 h-5" /> Cài Đặt
          </h2>
          <button onClick={() => setActiveTab('accounts')} className={`text-left px-4 py-3 rounded-xl font-medium transition-colors ${activeTab === 'accounts' ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20' : 'text-slate-600 hover:bg-slate-200'}`}>Tài Khoản Email</button>
          <button onClick={() => setActiveTab('content')} className={`text-left px-4 py-3 rounded-xl font-medium transition-colors ${activeTab === 'content' ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20' : 'text-slate-600 hover:bg-slate-200'}`}>Nội dung ưu tiên</button>
          <button onClick={() => setActiveTab('system')} className={`text-left px-4 py-3 rounded-xl font-medium transition-colors ${activeTab === 'system' ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20' : 'text-slate-600 hover:bg-slate-200'}`}>Hệ thống máy tính</button>
        </div>

        <div className="flex-1 p-8 overflow-y-auto relative bg-white custom-scrollbar w-full">
          <button onClick={onClose} className="absolute top-6 right-6 p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors z-10">
            <X className="w-5 h-5" />
          </button>
          {activeTab === 'accounts' && (
            <div className="space-y-6 pt-2">
              <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4">Email Liên Kết</h3>
              <div className="space-y-3">
                {['work@company.com', 'personal@gmail.com'].map(email => (
                  <div key={email} className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 border border-slate-100 rounded-2xl bg-white shadow-sm gap-2">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center shrink-0">
                        <Mail className="w-4 h-4 text-indigo-500" />
                      </div>
                      <span className="font-semibold text-slate-700 break-all">{email}</span>
                    </div>
                    <span className="text-[11px] font-bold px-2 py-1 bg-emerald-50 text-emerald-600 border border-emerald-100 rounded-full w-fit uppercase tracking-wide">Syncing</span>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <button className="flex items-center justify-center w-full gap-2 py-3 border-2 border-dashed border-slate-200 rounded-2xl text-slate-500 font-semibold hover:border-indigo-400 hover:text-indigo-500 transition-colors bg-white">
                  <Plus className="w-5 h-5" /> Kết nối tài khoản mới
                </button>
              </div>
            </div>
          )}
          {activeTab === 'content' && (
             <div className="space-y-8 pt-2">
               {/* === MỐI QUAN TÂM (TAG SYSTEM) === */}
               <div>
                 <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-6">Mối quan tâm</h3>
                 <p className="text-sm text-slate-500 mb-4">Agent sẽ ưu tiên lọc tin tức, email và đề xuất theo các chủ đề bạn quan tâm.</p>

                 {/* Tag Input */}
                 <div className="flex gap-2 mb-5">
                   <div className="relative flex-1">
                     <Hash className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                     <input
                       type="text"
                       value={tagInput}
                       onChange={(e) => setTagInput(e.target.value)}
                       onKeyDown={(e) => e.key === 'Enter' && addTag()}
                       placeholder="Nhập chủ đề, ví dụ: Tài chính, DevOps..."
                       className="w-full bg-white border border-slate-200 rounded-xl py-3 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 text-slate-800 transition-all placeholder:text-slate-400"
                     />
                   </div>
                   <button
                     onClick={addTag}
                     disabled={!tagInput.trim()}
                     className="px-5 py-3 bg-indigo-500 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-indigo-500/20 shrink-0"
                   >
                     <Plus className="w-4 h-4" />
                   </button>
                 </div>

                 {/* Tag Chips */}
                 <div className="flex flex-wrap gap-2">
                   {interestTags.map(tag => (
                     <span key={tag} className="group inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-50 border border-indigo-100 text-indigo-700 rounded-xl text-sm font-semibold hover:bg-indigo-100 transition-colors">
                       <Hash className="w-3.5 h-3.5 text-indigo-400" />
                       {tag}
                       <button onClick={() => removeTag(tag)} className="ml-1 p-0.5 rounded-full text-indigo-300 hover:text-red-500 hover:bg-red-50 transition-colors">
                         <X className="w-3.5 h-3.5" />
                       </button>
                     </span>
                   ))}
                   {interestTags.length === 0 && (
                     <p className="text-sm text-slate-400 italic py-2">Chưa có chủ đề nào. Hãy thêm ở trên!</p>
                   )}
                 </div>
               </div>

               {/* === BỘ LỌC ĐỀ XUẤT (GIỮ LẠI TOGGLE) === */}
               <div>
                 <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-6">Lọc đề xuất hành động</h3>
                 <div className="p-5 border border-slate-100 rounded-2xl bg-white shadow-sm space-y-4">
                   <div className="flex justify-between items-center"><span className="text-slate-600 font-medium text-sm">Công việc & Hành chính</span><Toggle active={settings.suggestWork} onClick={() => toggleSetting('suggestWork')} /></div>
                   <div className="flex justify-between items-center"><span className="text-slate-600 font-medium text-sm">Đời sống & Cá nhân</span><Toggle active={settings.suggestLife} onClick={() => toggleSetting('suggestLife')} /></div>
                 </div>
               </div>

               {/* === NGỮ CẢNH CÁ NHÂN === */}
               <div>
                 <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-4">Mô tả lối sống (Ngữ cảnh)</h3>
                 <textarea className="w-full h-32 p-4 border border-slate-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-700 resize-none bg-slate-50 text-sm leading-relaxed" placeholder="Tôi là một lập trình viên..." defaultValue="Tôi là một lập trình viên Web (Python, React). Ưu tiên các email về dự án lên hàng đầu. Tóm tắt các email quảng cáo thành 1 câu."></textarea>
               </div>
             </div>
          )}
          {activeTab === 'system' && (
             <div className="space-y-6 pt-2">
               <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-6">Desktop App</h3>
               <div className="space-y-3">
                 <div className="flex justify-between items-center p-5 border border-slate-100 rounded-2xl bg-white shadow-sm">
                   <div className="pr-4"><h4 className="font-bold text-slate-700">Auto-start với hệ điều hành</h4><p className="text-xs text-slate-500 mt-1">Nạp dữ liệu mầm khi máy tính bắt đầu bật</p></div>
                   <Toggle active={settings.runWithWindows} onClick={() => toggleSetting('runWithWindows')} />
                 </div>
                 <div className="flex justify-between items-center p-5 border border-slate-100 rounded-2xl bg-white shadow-sm">
                   <div className="pr-4"><h4 className="font-bold text-slate-700">Chạy nền hệ thống</h4><p className="text-xs text-slate-500 mt-1">Chỉ ẩn vào khay System Tray khi ấn nút [X]</p></div>
                   <Toggle active={settings.closeOnExit} onClick={() => toggleSetting('closeOnExit')} />
                 </div>
               </div>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};


// --- APP MAIN COMPONENT ---
export default function AgentDashboard() {
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  
  // Trạng thái các Panel trượt (Sidebar Con)
  const [activePanel, setActivePanel] = useState<'none' | 'chat' | 'notif' | 'email'>('none');

  const togglePanel = (panel: 'chat' | 'notif' | 'email') => {
    setActivePanel(prev => prev === panel ? 'none' : panel);
  }

  return (
    <div className="h-screen w-[1200px] flex bg-[#f8fafc] font-sans text-slate-800 overflow-hidden relative">
      
      {/* 
        ======== SLIDER BAR CHÍNH (VERTICAL SIDEBAR) ======== 
      */}
      <aside className="w-[72px] bg-[#1e1e2d] h-full flex flex-col items-center py-6 shrink-0 shadow-xl z-40 justify-between">
        <div className="flex flex-col items-center gap-8 w-full">
          {/* Logo */}
          <div className="w-12 h-12 bg-indigo-500 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 cursor-pointer hover:scale-105 transition-transform" onClick={() => setActivePanel('none')} title="Dashboard">
            <LayoutGrid className="w-6 h-6" />
          </div>
          
          <div className="w-8 h-[1px] bg-slate-700/50"></div>

          {/* Công cụ chính */}
          <div className="flex flex-col gap-6 w-full items-center">
            <button 
              onClick={() => togglePanel('notif')}
              className={`relative w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${activePanel === 'notif' ? "bg-white text-[#1e1e2d] shadow-lg" : "text-slate-400 hover:bg-slate-700/50 hover:text-white"}`}
              title="Thông báo hệ thống"
            >
              <Bell className="w-6 h-6" />
              <span className="absolute top-2 right-2.5 w-2.5 h-2.5 bg-pink-500 border-[2px] border-[#1e1e2d] rounded-full"></span>
            </button>

            <button 
              onClick={() => togglePanel('email')}
              className={`relative w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${activePanel === 'email' ? "bg-white text-[#1e1e2d] shadow-lg" : "text-slate-400 hover:bg-slate-700/50 hover:text-white"}`}
              title="Quản lý Hộp thư"
            >
              <Mail className="w-6 h-6" />
              <span className="absolute top-2 right-2 w-4 h-4 bg-indigo-500 border-[2px] border-[#1e1e2d] text-[9px] font-bold text-white flex items-center justify-center rounded-full">4</span>
            </button>

            <button 
              onClick={() => togglePanel('chat')}
              className={`relative w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${activePanel === 'chat' ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30" : "text-slate-400 hover:bg-slate-700/50 hover:text-white"}`}
              title="Trợ lý AI"
            >
              <MessageSquare className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Nút cài đặt (Dưới cùng) */}
        <button 
          onClick={() => setIsConfigOpen(true)}
          className="w-12 h-12 rounded-2xl text-slate-400 hover:bg-slate-700/50 hover:text-white flex items-center justify-center transition-all"
          title="Cấu hình hệ thống"
        >
          <Settings className="w-6 h-6" />
        </button>
      </aside>

      {/* 
        ======== MAIN DASHBOARD CỐT LÕI (GIẢI PHÓNG KHÔNG GIAN) ======== 
      */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        <header className="px-8 py-6 flex justify-between items-center shrink-0">
          <div>
            <h1 className="text-2xl font-black text-slate-800 tracking-tight">Nexus Workspace</h1>
            <p className="text-sm font-medium text-slate-500 mt-1">Hello, hôm nay bạn có <span className="text-indigo-500 font-bold">12</span> điểm ảnh hưởng cần xử lý!</p>
          </div>
        </header>

        <div className="flex-1 overflow-auto px-8 pb-8 custom-scrollbar">
          <div className="h-full grid grid-cols-12 gap-6 min-h-[600px]">
            
            {/* Cột Trái (Thời Tiết, Lịch, Tin tức) - 7 cột */}
            <div className="col-span-7 flex flex-col gap-6 h-full">
               <div className="grid grid-cols-2 gap-6 h-[180px] shrink-0">
                <Card title="Phân Tích Khí Hậu" icon={Cloud} className="border-transparent shadow-md hover:shadow-lg transition-shadow">
                  <div className="flex flex-col items-center justify-center h-full pt-2">
                    <span className="text-5xl font-black text-slate-800">28°C</span>
                    <span className="text-[15px] font-semibold text-slate-500 mt-2">Cần Thơ, VN</span>
                    <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 mt-1">Nhiều mây rải rác</span>
                  </div>
                </Card>
                <Card title="Hôm Nay" icon={Calendar} className="border-transparent shadow-md hover:shadow-lg transition-shadow">
                  <div className="flex flex-col items-center justify-center h-full text-center pt-2">
                    <span className="text-sm font-bold text-slate-400 uppercase tracking-widest">Thứ Ba</span>
                    <span className="text-6xl font-black text-slate-800 my-1">14</span>
                    <span className="text-xs font-bold text-slate-500 tracking-wide uppercase">Tháng 4, 2026</span>
                  </div>
                </Card>
              </div>

              <Card title="Tin Tức Đã Lọc (Thông Minh)" icon={Newspaper} className="flex-1 border-transparent shadow-md hover:shadow-lg transition-shadow">
                <div className="space-y-5 pt-2">
                  <div className="group border-b border-slate-100 pb-5 hover:border-indigo-100 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] font-black text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md uppercase tracking-wider">React FW</span>
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1"><RotateCw className="w-3 h-3"/> Cập nhật 10p trước</span>
                    </div>
                    <h4 className="text-base font-bold text-slate-800 leading-snug group-hover:text-indigo-600 transition-colors">Vercel phát hành React 19 bản chính thức tích hợp React Compiler x3 tốc độ Render.</h4>
                    <p className="text-sm text-slate-500 mt-2 leading-relaxed">Framework Frontend phổ biến nhất vừa đại tu toàn diện, xoá bỏ useMemo, useCallback thông qua cơ chế tự động biên dịch ở cấp độ AST.</p>
                  </div>

                  <div className="group border-b border-slate-100 pb-5 hover:border-indigo-100 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] font-black text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md uppercase tracking-wider">Backend</span>
                    </div>
                    <h4 className="text-base font-bold text-slate-800 leading-snug group-hover:text-emerald-600 transition-colors">Django 5.1 update Async ORM siêu tốc cùng gRPC.</h4>
                  </div>
                </div>
              </Card>
            </div>

            {/* Cột Phải (Hành Động Khẩn & Gợi Ý) - 5 cột */}
            <div className="col-span-5 flex flex-col h-full">
              <Card title="Bộ não Hành động" icon={Lightbulb} className="h-full border-none shadow-xl bg-gradient-to-b from-[#1e1e2d] to-[#11111a] p-0">
                <div className="flex flex-col gap-4 h-full p-6 text-white pb-8">
                  <div className="mb-2">
                    <p className="text-sm font-semibold text-indigo-300">Nex AI dự báo & lên kế hoạch</p>
                    <h2 className="text-2xl font-black mt-1">Hôm nay nên làm gì?</h2>
                  </div>

                  <div className="flex items-start gap-4 bg-white/5 p-4 rounded-2xl border border-white/10 hover:bg-white/10 transition-colors">
                    <div className="w-10 h-10 rounded-full bg-pink-500/20 flex items-center justify-center shrink-0">
                      <CheckCircle2 className="w-5 h-5 text-pink-400" />
                    </div>
                    <div>
                      <p className="text-[15px] font-bold text-white mb-1">Email dự án khẩn</p>
                      <p className="text-sm text-slate-300 leading-relaxed">Có 2 email từ PM Nguyễn chưa trả lời, liên quan đến tiến độ dự án. Trả lời ngay?</p>
                      <button className="mt-3 px-4 py-2 bg-pink-500 text-white rounded-xl text-xs font-bold hover:bg-pink-600 transition-colors shadow-lg shadow-pink-500/30">Auto-Draft (Trợ lý viết)</button>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-4 bg-white/5 p-4 rounded-2xl border border-white/10 hover:bg-white/10 transition-colors">
                    <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center shrink-0">
                      <Cloud className="w-5 h-5 text-cyan-400" />
                    </div>
                    <div>
                      <p className="text-[15px] font-bold text-white mb-1">Lịch đi ra ngoài</p>
                      <p className="text-sm text-slate-300 leading-relaxed">Chiều nay lúc 15:00 có khả năng cao mưa, bạn nên chủ động di chuyển trước 14:30.</p>
                    </div>
                  </div>

                  <div className="mt-auto pt-4 relative">
                    <div className="absolute -top-6 left-0 right-0 h-4 bg-gradient-to-t from-[#11111a] to-transparent pointer-events-none"></div>
                    <button className="w-full bg-white text-[#1e1e2d] font-bold py-3.5 rounded-2xl hover:bg-indigo-50 transition-transform active:scale-95 shadow-[0_0_20px_rgba(255,255,255,0.1)] flex items-center justify-center gap-2">
                       Chấp thuận toàn bộ <CheckCircle2 className="w-4 h-4"/>
                    </button>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>

        {/* 
          ======== CÁC PANEL MỞ RỘNG (SLIDE-OVERS TỪ PHẢI) ======== 
        */}

        {/* 1. NOTIFICATION PANEL */}
        <div className={`absolute top-0 right-0 h-full w-[380px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col transition-transform duration-300 ease-in-out ${activePanel === 'notif' ? "translate-x-0" : "translate-x-full"}`}>
          <div className="flex justify-between items-center bg-slate-50 border-b border-slate-100 p-5 shrink-0">
            <h2 className="font-bold text-slate-800 flex items-center gap-2 text-lg">
              <Bell className="w-5 h-5 text-pink-500" /> Hệ thống cảnh báo
            </h2>
            <button onClick={() => setActivePanel('none')} className="p-2 bg-white text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
             <div className="p-4 bg-red-50 border border-red-100 rounded-2xl">
                <p className="text-sm font-bold text-red-700">Deadline báo cáo tháng QA</p>
                <p className="text-xs text-red-600/80 mt-1">Còn 2 giờ nữa</p>
             </div>
             <div className="p-4 bg-white border border-slate-100 rounded-2xl shadow-sm">
                <p className="text-sm font-bold text-slate-800">Cập nhật Windows ngầm</p>
                <p className="text-xs text-slate-500 mt-1">Đã hoàn tất lúc sáng nay</p>
             </div>
          </div>
        </div>

        {/* 2. EMAIL PANEL */}
        <div className={`absolute top-0 right-0 h-full w-[420px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col transition-transform duration-300 ease-in-out ${activePanel === 'email' ? "translate-x-0" : "translate-x-full"}`}>
          <div className="flex justify-between items-center bg-slate-50 border-b border-slate-100 p-5 shrink-0">
            <h2 className="font-bold text-slate-800 flex items-center gap-2 text-lg">
              <Mail className="w-5 h-5 text-indigo-500" /> Hộp thư chờ duyệt (4)
            </h2>
            <button onClick={() => setActivePanel('none')} className="p-2 bg-white text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-3 bg-slate-50/50">
             {[
               { from: 'PM Nguyen (Project X)', sub: 'Urgent: Review Pull Request Vercel #42 để anh chốt Release', time: '10p trước', urgent: true },
               { from: 'Cloudflare', sub: 'Hóa đơn tháng 4. Your bill is ready.', time: '1h trước', urgent: false },
               { from: 'GitHub', sub: 'Deploy successful to production', time: '2h trước', urgent: false },
             ].map((mail, i) => (
                <div key={i} className={`p-4 border ${mail.urgent ? 'border-indigo-200 bg-indigo-50/40 shadow-sm' : 'border-slate-200 bg-white'} rounded-2xl cursor-pointer hover:border-indigo-400 transition-colors`}>
                  <div className="flex justify-between items-start mb-2 gap-2">
                    <span className={`text-[13px] font-bold ${mail.urgent ? 'text-indigo-900' : 'text-slate-800'}`}>{mail.from}</span>
                    <span className="text-[10px] font-semibold text-slate-400 shrink-0 bg-slate-100 px-2 py-0.5 rounded-full">{mail.time}</span>
                  </div>
                  <p className={`text-[13px] leading-relaxed ${mail.urgent ? 'text-indigo-800 font-medium' : 'text-slate-600'}`}>{mail.sub}</p>
                </div>
             ))}
          </div>
        </div>

        {/* 3. CHAT MÁY HỌC PANEL */}
        <div className={`absolute top-0 right-0 h-full w-[450px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col transition-transform duration-300 ease-in-out ${activePanel === 'chat' ? "translate-x-0" : "translate-x-full"}`}>
          <div className="flex justify-between items-center bg-white border-b border-slate-100 p-5 shrink-0 shadow-sm z-10 relative">
            <h2 className="font-bold text-slate-800 flex items-center gap-2 text-lg">
              <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-sm shadow-emerald-500/50"></span>
              Agent Chatbox
            </h2>
            <button onClick={() => setActivePanel('none')} className="p-2 text-slate-400 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 rounded-xl transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-6 p-6 custom-scrollbar bg-slate-50/80">
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 shadow-md">
                <User className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white border border-slate-100 p-4 rounded-2xl rounded-tl-sm text-[13px] text-slate-800 shadow-sm leading-relaxed max-w-[85%] font-medium">
                Hãy tóm tắt và lọc những gì quan trọng nhất hôm nay nhé.
              </div>
            </div>
            <div className="flex gap-3 flex-row-reverse">
              <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center shrink-0 shadow-md shadow-indigo-500/30 border border-indigo-400">
                <LayoutGrid className="w-4 h-4 text-white" />
              </div>
              <div className="bg-[#1e1e2d] text-white p-4 rounded-2xl rounded-tr-sm text-[13px] shadow-lg leading-relaxed max-w-[85%] font-medium">
                Có 2 vấn đề rủi ro cao:
                <br/><br/>
                1. 1 Email khẩn từ PM cần Review Code, nếu không rớt tiến độ Sprint.
                <br/>
                2. Bão đang kéo đến, bạn nên đổi ca họp hoặc di chuyển ngay.
              </div>
            </div>
          </div>
          
          <div className="p-5 bg-white border-t border-slate-100 shrink-0">
            <div className="relative flex items-center shadow-sm">
              <input 
                type="text" 
                placeholder="Ví dụ: Gửi thư xin phép PM delay review..." 
                className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pr-14 pl-5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 text-slate-800 transition-all"
              />
              <button className="absolute right-2 p-2.5 bg-indigo-500 text-white rounded-xl hover:bg-indigo-600 active:scale-95 transition-all shadow-md shadow-indigo-500/30 flex items-center justify-center">
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Nền làm mờ nội dung phía sau nếu có Panel nào đó đang mở */}
        {activePanel !== 'none' && (
          <div 
            onClick={() => setActivePanel('none')}
            className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px] z-20 cursor-pointer animate-in fade-in duration-200" 
          />
        )}
      </div>

      <ConfigPanel isOpen={isConfigOpen} onClose={() => setIsConfigOpen(false)} />

      {/* Global CSS scrollbar */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 20px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: #94a3b8; }
      `}} />
    </div>
  );
}
