"use client";

import React from 'react';
import { Download, Bot, Calendar, Mail, Zap, ChevronRight, Shield, Globe } from 'lucide-react';
import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      {/* Header */}
      <header className="fixed top-0 w-full bg-white/80 backdrop-blur-md z-50 border-b border-slate-200/50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
              <Bot className="w-6 h-6" />
            </div>
            <span className="text-xl font-black tracking-tight text-slate-800">Nexus Workspace</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 font-medium text-sm text-slate-600">
            <a href="#features" className="hover:text-indigo-600 transition-colors">Tính năng</a>
            <a href="#how-it-works" className="hover:text-indigo-600 transition-colors">Cách hoạt động</a>
          </nav>
          <a
            href="/downloads/NexusWorkspace-Client.zip"
            className="hidden md:flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-full font-bold text-sm transition-all shadow-md hover:shadow-xl hover:shadow-indigo-500/20 active:scale-95"
          >
            <Download className="w-4 h-4" />
            Tải Client Agent
          </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-40 pb-20 px-6 relative overflow-hidden">
        {/* Decorative background elements */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-indigo-500/10 blur-[100px] rounded-full pointer-events-none"></div>
        
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-sm font-bold mb-8">
            <span className="flex h-2 w-2 rounded-full bg-indigo-500 animate-pulse"></span>
            Nexus Agent v1.0 đã sẵn sàng
          </div>
          
          <h1 className="text-5xl md:text-7xl font-black text-slate-900 tracking-tight leading-[1.1] mb-8">
            Không gian làm việc <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-cyan-500">
              điều khiển bằng AI
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            Nexus Workspace là trợ lý AI cá nhân mạnh mẽ, giúp bạn tự động hóa quản lý email, sắp xếp lịch hẹn và cập nhật tin tức công nghệ hoàn toàn tự động.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="/downloads/NexusWorkspace-Client.zip"
              className="group flex items-center justify-center gap-3 bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-full font-bold text-lg transition-all shadow-xl shadow-indigo-500/20 hover:shadow-2xl hover:shadow-indigo-500/30 active:scale-95 w-full sm:w-auto"
            >
              <Download className="w-5 h-5 group-hover:-translate-y-1 transition-transform" />
              Tải xuống bản cài đặt (.exe)
            </a>
            <a
              href="#features"
              className="flex items-center justify-center gap-2 bg-white border-2 border-slate-200 hover:border-slate-300 text-slate-700 px-8 py-4 rounded-full font-bold text-lg transition-all active:scale-95 w-full sm:w-auto"
            >
              Tìm hiểu thêm
            </a>
          </div>
          <p className="text-sm text-slate-400 mt-6 flex items-center justify-center gap-2">
            <Shield className="w-4 h-4" /> Hỗ trợ Windows 10/11 (64-bit)
          </p>
        </div>
      </section>

      {/* Screenshot / App Preview Section */}
      <section className="max-w-6xl mx-auto px-6 mb-32 relative z-10">
        <div className="bg-slate-900 rounded-[2.5rem] p-4 shadow-2xl shadow-indigo-900/20 border border-slate-800">
          <div className="bg-[#1e1e2d] rounded-[2rem] overflow-hidden aspect-[16/9] relative border border-slate-700 flex items-center justify-center">
            {/* Mockup Placeholder */}
            <div className="text-center">
              <Bot className="w-20 h-20 text-slate-600 mx-auto mb-4" />
              <h3 className="text-2xl font-bold text-slate-400">Giao diện Nexus Agent</h3>
              <p className="text-slate-500 mt-2">Hoạt động ngầm và tương tác trực quan</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-white px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-black text-slate-900 tracking-tight mb-6">Tự động hóa toàn diện</h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">Trợ lý ảo được thiết kế riêng biệt để hiểu ngữ cảnh của bạn, thay bạn xử lý các tác vụ lặp đi lặp lại.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:border-indigo-100 hover:bg-indigo-50/30 transition-colors">
              <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center shadow-sm border border-slate-100 mb-6 text-indigo-600">
                <Mail className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Email Thông Minh</h3>
              <p className="text-slate-600 leading-relaxed">
                Tự động phân loại, tóm tắt và đánh giá mức độ khẩn cấp của các email đến. Soạn thảo email phản hồi chuyên nghiệp chỉ với 1 click.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:border-indigo-100 hover:bg-indigo-50/30 transition-colors">
              <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center shadow-sm border border-slate-100 mb-6 text-indigo-600">
                <Calendar className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Quản Lý Lịch Trình</h3>
              <p className="text-slate-600 leading-relaxed">
                Phát hiện yêu cầu họp từ tin nhắn/email, kiểm tra lịch trống và tự động đề xuất tạo lịch hẹn vào khung giờ phù hợp nhất.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:border-indigo-100 hover:bg-indigo-50/30 transition-colors">
              <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center shadow-sm border border-slate-100 mb-6 text-indigo-600">
                <Zap className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Đề Xuất Chủ Động</h3>
              <p className="text-slate-600 leading-relaxed">
                Hệ thống chủ động đưa ra các đề xuất công việc, nhắc nhở thời tiết trước khi ra ngoài và tổng hợp tin tức theo mối quan tâm cá nhân.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-24 bg-slate-900 text-white px-6">
        <div className="max-w-5xl mx-auto text-center">
          <h2 className="text-3xl md:text-5xl font-black tracking-tight mb-16">Cách hoạt động</h2>
          
          <div className="grid md:grid-cols-3 gap-12 text-left relative">
            {/* Line connecting steps */}
            <div className="hidden md:block absolute top-8 left-[10%] right-[10%] h-[2px] bg-slate-800"></div>

            <div className="relative z-10">
              <div className="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center text-2xl font-black mb-6 shadow-xl shadow-indigo-500/20 border-4 border-slate-900">1</div>
              <h3 className="text-xl font-bold mb-3">Tải và Cài đặt</h3>
              <p className="text-slate-400">Tải bộ cài đặt Desktop Client và khởi chạy ứng dụng nền trên máy tính của bạn.</p>
            </div>

            <div className="relative z-10">
              <div className="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center text-2xl font-black mb-6 shadow-xl shadow-indigo-500/20 border-4 border-slate-900">2</div>
              <h3 className="text-xl font-bold mb-3">Kết nối Dịch vụ</h3>
              <p className="text-slate-400">Đăng nhập tài khoản Google để đồng bộ Email và Lịch, cung cấp ngữ cảnh cá nhân.</p>
            </div>

            <div className="relative z-10">
              <div className="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center text-2xl font-black mb-6 shadow-xl shadow-indigo-500/20 border-4 border-slate-900">3</div>
              <h3 className="text-xl font-bold mb-3">Trải nghiệm AI</h3>
              <p className="text-slate-400">Agent sẽ tự động chạy ngầm, theo dõi và gửi đề xuất ngay khi có công việc cần xử lý.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 relative overflow-hidden bg-indigo-600 text-white text-center">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
        <div className="max-w-3xl mx-auto relative z-10">
          <h2 className="text-4xl md:text-6xl font-black tracking-tight mb-8">Sẵn sàng để tối ưu năng suất?</h2>
          <p className="text-xl text-indigo-100 mb-12">Bắt đầu sử dụng Nexus Workspace ngay hôm nay và trải nghiệm sức mạnh của AI trong công việc thực tế.</p>
          <a
            href="/downloads/NexusWorkspace-Client.zip"
            className="inline-flex items-center justify-center gap-3 bg-white text-indigo-600 hover:bg-slate-50 px-10 py-5 rounded-full font-black text-xl transition-all shadow-2xl active:scale-95"
          >
            <Download className="w-6 h-6" />
            Tải xuống thư mục EXE
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-950 text-slate-400 py-12 text-center text-sm border-t border-slate-900">
        <p>© 2026 Nexus Workspace. All rights reserved.</p>
      </footer>
    </div>
  );
}
