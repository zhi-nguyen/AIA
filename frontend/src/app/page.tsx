"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  getWeather, getProposals, getLinkedAccounts, deleteLinkedAccount,
  getGoogleAuthUrl, initSession, getUserProfile, createUserProfile, getTokenUsage, type LinkedAccount
} from '@/lib/api';
import MailPanel from '@/components/MailPanel';
import AgentChatPanel from '@/components/AgentChatPanel';
import CalendarSidebar from '@/components/CalendarSidebar';
import ProposalSidebar from '@/components/ProposalSidebar';
import { useChat } from '@/hooks/useChat';
import { useProposals } from '@/hooks/useProposals';
import {
  Settings, Mail, Calendar, Cloud, Newspaper,
  Bell, Lightbulb, MessageSquare, Plus, X,
  ToggleRight, ToggleLeft, Send, CheckCircle2, User, LayoutGrid, RotateCw, Hash, Link2, ExternalLink, Globe, MapPin, Save, Zap, Activity, Cpu, TrendingUp
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
  const [interestTags, setInterestTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [savedUrls, setSavedUrls] = useState<string[]>([]);
  const [userAddress, setUserAddress] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isProfileLoaded, setIsProfileLoaded] = useState(false);

  const loadProfile = useCallback(async () => {
    try {
      const resp = await getUserProfile();
      const profile = resp.profile;
      if (profile) {
        setInterestTags(profile.interests || []);
        setSavedUrls(profile.preferred_news_sources || []);
        setUserAddress(profile.address || '');
        if (profile.work_style) {
          try {
            setSettings(JSON.parse(profile.work_style));
          } catch {}
        }
      }
    } catch (e) {
      console.error('Failed to load profile', e);
    }
    setIsProfileLoaded(true);
  }, []);

  useEffect(() => {
    if (isOpen && !isProfileLoaded) loadProfile();
  }, [isOpen, isProfileLoaded, loadProfile]);

  const handleSaveConfig = async () => {
    setIsSaving(true);
    try {
      await createUserProfile({
        name: "User", // Can be extended with a real name input later
        occupation: "",
        interests: interestTags,
        preferred_news_sources: savedUrls,
        work_style: JSON.stringify(settings),
        address: userAddress,
      });
      alert("Đã lưu thông tin cấu hình");
    } catch (e) {
      console.error('Failed to save profile', e);
      alert("Lỗi khi lưu cấu hình");
    } finally {
      setIsSaving(false);
    }
  };

  // --- Real API: Tài khoản email ---
  const [accounts, setAccounts] = useState<LinkedAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);

  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true);
    try {
      const data = await getLinkedAccounts();
      setAccounts(data.accounts || []);
    } catch { setAccounts([]); }
    setAccountsLoading(false);
  }, []);

  useEffect(() => {
    if (isOpen && accounts.length === 0) loadAccounts();
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-reload khi user quay lại app sau OAuth (chỉ khi panel đang mở)
  useEffect(() => {
    if (!isOpen) return;
    const onFocus = () => loadAccounts();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [isOpen, loadAccounts]);

  const handleAddAccount = async () => {
    try {
      const data = await getGoogleAuthUrl();
      if (data.url) {
        // Tauri: mở bằng trình duyệt hệ thống
        try {
          const { open } = await import('@tauri-apps/plugin-shell');
          await open(data.url);
        } catch {
          // Fallback cho môi trường dev browser thuần
          window.location.href = data.url;
        }
      }
    } catch (e) { console.error('OAuth error:', e); }
  };

  const handleDeleteAccount = async (accountId: string) => {
    try {
      await deleteLinkedAccount(accountId);
      setAccounts(prev => prev.filter(a => a.id !== accountId));
    } catch (e) { console.error('Delete error:', e); }
  };
  const [urlInput, setUrlInput] = useState('');

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

  const addUrl = () => {
    let trimmed = urlInput.trim();
    if (!trimmed) return;
    // Tự động thêm https:// nếu thiếu
    if (!/^https?:\/\//.test(trimmed)) trimmed = 'https://' + trimmed;
    if (!savedUrls.includes(trimmed)) {
      setSavedUrls(prev => [...prev, trimmed]);
      setUrlInput('');
    }
  };

  const removeUrl = (url: string) => {
    setSavedUrls(prev => prev.filter(u => u !== url));
  };

  const extractDomain = (url: string) => {
    try { return new URL(url).hostname.replace('www.', ''); } catch { return url; }
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

        <div className="flex-1 flex flex-col relative bg-white w-full">
          {/* Nút Đóng (X) luôn cố định ở góc */}
          <div className="absolute top-4 right-4 z-20">
            <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors bg-white/80 backdrop-blur-sm shadow-sm border border-slate-100">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
            {activeTab === 'accounts' && (
              <div className="space-y-6 pt-2">
                <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4">Email Liên Kết</h3>
                <div className="space-y-3">
                  {accountsLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <RotateCw className="w-6 h-6 text-indigo-400 animate-spin" />
                      <span className="ml-3 text-sm text-slate-500 font-medium">Đang tải...</span>
                    </div>
                  ) : accounts.length === 0 ? (
                    <div className="text-center py-12">
                      <Mail className="w-12 h-12 text-slate-200 mx-auto mb-3" />
                      <p className="text-sm text-slate-500">Chưa kết nối tài khoản email nào.</p>
                      <p className="text-xs text-slate-400 mt-1">Nhấn nút bên dưới để bắt đầu.</p>
                    </div>
                  ) : (
                    accounts.map(acc => (
                      <div key={acc.id} className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 border border-slate-100 rounded-2xl bg-white shadow-sm gap-2">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center shrink-0">
                            <Mail className="w-4 h-4 text-indigo-500" />
                          </div>
                          <div className="flex flex-col">
                            <span className="font-semibold text-slate-700 break-all">{acc.email}</span>
                            {acc.is_primary && <span className="text-[10px] text-indigo-500 font-bold uppercase">Primary</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-bold px-2 py-1 bg-emerald-50 text-emerald-600 border border-emerald-100 rounded-full uppercase tracking-wide">Syncing</span>
                          <button
                            onClick={() => {
                              const msg = acc.is_primary
                                ? `Xoá tài khoản chính "${acc.email}"? ${accounts.length > 1 ? 'Tài khoản khác sẽ được promote thành primary.' : 'Bạn sẽ cần kết nối lại email.'}`
                                : `Gỡ liên kết "${acc.email}"?`;
                              if (window.confirm(msg)) handleDeleteAccount(acc.id);
                            }}
                            className="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            title="Gỡ liên kết"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-4">
                  <button onClick={handleAddAccount} className="flex items-center justify-center w-full gap-2 py-3 border-2 border-dashed border-slate-200 rounded-2xl text-slate-500 font-semibold hover:border-indigo-400 hover:text-indigo-500 transition-colors bg-white">
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

                {/* === TRANG WEB CỤ THỂ === */}
                <div>
                  <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-4 flex items-center gap-2">
                    <Globe className="w-5 h-5 text-indigo-400" /> Trang web cụ thể
                  </h3>
                  <p className="text-sm text-slate-500 mb-4">Thêm các trang web mà Agent sẽ ưu tiên quét và tổng hợp nội dung cho bạn.</p>

                  {/* URL Input */}
                  <div className="flex gap-2 mb-5">
                    <div className="relative flex-1">
                      <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        type="text"
                        value={urlInput}
                        onChange={(e) => setUrlInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addUrl()}
                        placeholder="Dán link, ví dụ: https://techcrunch.com"
                        className="w-full bg-white border border-slate-200 rounded-xl py-3 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 text-slate-800 transition-all placeholder:text-slate-400 font-mono"
                      />
                    </div>
                    <button
                      onClick={addUrl}
                      disabled={!urlInput.trim()}
                      className="px-5 py-3 bg-indigo-500 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-indigo-500/20 shrink-0"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>

                  {/* URL List */}
                  <div className="space-y-2">
                    {savedUrls.map(url => (
                      <div key={url} className="group flex items-center gap-3 p-3 bg-white border border-slate-100 rounded-xl hover:border-indigo-200 hover:bg-indigo-50/30 transition-all">
                        <div className="w-8 h-8 rounded-lg bg-slate-100 group-hover:bg-indigo-100 flex items-center justify-center shrink-0 transition-colors">
                          <Globe className="w-4 h-4 text-slate-500 group-hover:text-indigo-500 transition-colors" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-slate-700 truncate">{extractDomain(url)}</p>
                          <p className="text-[11px] text-slate-400 font-mono truncate">{url}</p>
                        </div>
                        <a href={url} target="_blank" rel="noopener noreferrer" className="p-1.5 text-slate-300 hover:text-indigo-500 transition-colors" title="Mở trang web">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                        <button onClick={() => removeUrl(url)} className="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors" title="Xoá">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                    {savedUrls.length === 0 && (
                      <p className="text-sm text-slate-400 italic py-3 text-center">Chưa có trang web nào. Dán link ở trên để bắt đầu!</p>
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

                {/* === ĐỊA CHỈ === */}
                <div>
                  <h3 className="text-xl font-bold text-slate-800 border-b border-slate-100 pb-4 mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-indigo-400" /> Địa chỉ (Dùng cho Thời tiết)
                  </h3>
                  <div className="relative">
                    <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                    <input
                      type="text"
                      value={userAddress}
                      onChange={(e) => setUserAddress(e.target.value)}
                      placeholder="Nhập địa chỉ của bạn (VD: Quận 1, TPHCM)..."
                      className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3 pl-12 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 text-slate-700 transition-all"
                    />
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

          {/* Footer cố định cho tất cả các tab (Lưu Toàn bộ Config) */}
          <div className="p-4 border-t border-slate-100 bg-slate-50 flex justify-end shrink-0">
            <button
              onClick={handleSaveConfig}
              disabled={isSaving}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-xl font-bold shadow-md hover:bg-indigo-700 hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-wait"
            >
              {isSaving ? <RotateCw className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
              {isSaving ? 'Đang lưu...' : 'Lưu thiết lập'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- APP MAIN COMPONENT ---
export default function AgentDashboard() {
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const { proposals, approveProposal, dismissProposal } = useProposals();
  const [activePanel, setActivePanel] = useState<'none' | 'notif' | 'email' | 'chat' | 'calendar'>('none');

  // Chat state - lifted to page level so WebSocket persists
  const chatState = useChat();

  const togglePanel = (panel: 'chat' | 'notif' | 'email' | 'calendar') => {
    setActivePanel(prev => prev === panel ? 'none' : panel);
  }

  // === REAL API DATA ===
  const [weatherData, setWeatherData] = useState<any>(null);
  const [tokenUsage, setTokenUsage] = useState({ in: 0, out: 0 });
  const [dataLoading, setDataLoading] = useState(true);

  const loadTokens = async () => {
    try {
      const tokenRes = await getTokenUsage().catch(() => null);
      if (tokenRes) setTokenUsage({ in: tokenRes.tokens_in || 0, out: tokenRes.tokens_out || 0 });
    } catch {}
  };

  useEffect(() => {
    const loadDashboard = async () => {
      setDataLoading(true);
      try {
        await initSession();
        const weatherRes = await getWeather().catch(() => null);
        if (weatherRes) setWeatherData(weatherRes);
        await loadTokens();
      } catch (e) { console.error('Dashboard load error:', e); }
      setDataLoading(false);
    };
    loadDashboard();
  }, []);

  // Gọi api cập nhật token khi chat hoàn thành (khi loading chuyển từ true về false)
  useEffect(() => {
    if (!chatState.isLoading) {
      loadTokens();
    }
  }, [chatState.isLoading]);

  // Helper: parse weather
  const weatherTemp = weatherData?.weather?.data?.current?.temp_c;
  const weatherCity = weatherData?.address?.address_province || '—';
  const weatherDesc = weatherData?.weather?.data?.current?.condition?.text || 'Đang cập nhật...';

  // Helper: current date
  const now = new Date();
  const dayNames = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];
  const monthNames = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];

  // format tokens
  const formatToken = (num: number) => {
    if (num >= 1000000) return { val: (num / 1000000).toFixed(2), suffix: 'M' };
    if (num >= 1000) return { val: (num / 1000).toFixed(1), suffix: 'K' };
    return { val: num.toString(), suffix: '' };
  };
  const numTokenIn = formatToken(tokenUsage.in);
  const numTokenOut = formatToken(tokenUsage.out);
  const tokenLimit = 2000000;
  const tokenPercent = Math.min(Math.round(((tokenUsage.in + tokenUsage.out) / tokenLimit) * 100), 100);

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
              {proposals.length > 0 && <span className="absolute top-2 right-2.5 w-3 h-3 bg-pink-500 border-[2px] border-[#1e1e2d] rounded-full text-[0px]"></span>}
            </button>

            <button
              onClick={() => togglePanel('email')}
              className={`relative w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${activePanel === 'email' ? "bg-white text-[#1e1e2d] shadow-lg" : "text-slate-400 hover:bg-slate-700/50 hover:text-white"}`}
              title="Quản lý Hộp thư"
            >
              <Mail className="w-6 h-6" />
            </button>

            <button
              onClick={() => togglePanel('calendar')}
              className={`relative w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${activePanel === 'calendar' ? "bg-white text-[#1e1e2d] shadow-lg" : "text-slate-400 hover:bg-slate-700/50 hover:text-white"}`}
              title="Lịch hẹn"
            >
              <Calendar className="w-6 h-6" />
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
            <p className="text-sm font-medium text-slate-500 mt-1">Hello, hôm nay bạn có <span className="text-indigo-500 font-bold">{proposals.length}</span> đề xuất cần xử lý</p>
          </div>
        </header>

        <div className="flex-1 overflow-auto px-8 pb-8 custom-scrollbar">
          <div className="h-full grid grid-cols-12 gap-6 min-h-[600px]">

            {/* Cột Trái (Thời Tiết, Lịch, Tin tức) - 7 cột */}
            <div className="col-span-7 flex flex-col gap-6 h-full">
              <div className="grid grid-cols-2 gap-6 h-[180px] shrink-0">
                <Card title="Phân Tích Khí Hậu" icon={Cloud} className="border-transparent shadow-md hover:shadow-lg transition-shadow">
                  <div className="flex flex-col items-center justify-center h-full pt-2">
                    {weatherTemp != null ? (
                      <>
                        <span className="text-5xl font-black text-slate-800">{Math.round(weatherTemp)}°C</span>
                        <span className="text-[15px] font-semibold text-slate-500 mt-2">{weatherCity}</span>
                        <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 mt-1">{weatherDesc}</span>
                      </>
                    ) : (
                      <>
                        <Cloud className="w-10 h-10 text-slate-300 mb-2" />
                        <span className="text-sm text-slate-400 font-medium">{weatherData?.status === 'no_address' ? 'Cập nhật địa chỉ trong Settings' : 'Đang tải...'}</span>
                      </>
                    )}
                  </div>
                </Card>
                <Card title="Hôm Nay" icon={Calendar} className="border-transparent shadow-md hover:shadow-lg transition-shadow">
                  <div className="flex flex-col items-center justify-center h-full text-center pt-2">
                    <span className="text-sm font-bold text-slate-400 uppercase tracking-widest">{dayNames[now.getDay()]}</span>
                    <span className="text-6xl font-black text-slate-800 my-1">{now.getDate()}</span>
                    <span className="text-xs font-bold text-slate-500 tracking-wide uppercase">Tháng {monthNames[now.getMonth()]}, {now.getFullYear()}</span>
                  </div>
                </Card>
              </div>

              <Card title="Tin Tức Đã Lọc" icon={Newspaper} className="flex-1 border-transparent shadow-md hover:shadow-lg transition-shadow">
                <div className="space-y-5 pt-2">
                  <div className="group border-b border-slate-100 pb-5 hover:border-indigo-100 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] font-black text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md uppercase tracking-wider">React FW</span>
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1"><RotateCw className="w-3 h-3" /> Cập nhật 10p trước</span>
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
              <Card title="Token Usage & Analytics" icon={Cpu} className="h-full border-none shadow-xl bg-gradient-to-b from-[#1e1e2d] to-[#11111a] p-0">
                <div className="flex flex-col h-full p-6 text-white">
                  <div className="mb-6">
                    <p className="text-sm font-semibold text-emerald-400 flex items-center gap-2"><Activity className="w-4 h-4"/> Hệ thống đang phân bổ tài nguyên hiệu quả</p>
                    <h2 className="text-2xl font-black mt-1">Lưu lượng LLM (Tháng {now.getMonth() + 1})</h2>
                  </div>

                  {/* Token Stats */}
                  <div className="grid grid-cols-2 gap-4 mb-8">
                    <div className="bg-white/5 rounded-2xl p-4 border border-white/10 hover:bg-white/10 transition-colors">
                      <div className="flex items-center gap-2 mb-2 text-indigo-300">
                        <TrendingUp className="w-5 h-5"/>
                        <span className="text-xs font-bold uppercase tracking-wider">Token In</span>
                      </div>
                      <div className="text-3xl font-black">{numTokenIn.val}<span className="text-sm font-bold text-slate-400 ml-1">{numTokenIn.suffix}</span></div>
                      <p className="text-[11px] text-slate-400 mt-1">Tác vụ thu thập & tóm tắt</p>
                    </div>

                    <div className="bg-white/5 rounded-2xl p-4 border border-white/10 hover:bg-white/10 transition-colors">
                      <div className="flex items-center gap-2 mb-2 text-emerald-300">
                        <Zap className="w-5 h-5"/>
                        <span className="text-xs font-bold uppercase tracking-wider">Token Out</span>
                      </div>
                      <div className="text-3xl font-black">{numTokenOut.val}<span className="text-sm font-bold text-slate-400 ml-1">{numTokenOut.suffix}</span></div>
                      <p className="text-[11px] text-slate-400 mt-1">Suy luận & Phản hồi</p>
                    </div>
                  </div>

                  {/* Progress Bar Limit */}
                  <div className="mb-6 bg-white/5 rounded-2xl p-5 border border-white/10">
                    <div className="flex justify-between items-end mb-3">
                      <div>
                        <h4 className="text-sm font-bold text-slate-200">Giới hạn trong ngày ({formatToken(tokenLimit).val}{formatToken(tokenLimit).suffix})</h4>
                        <p className="text-xs text-slate-400 mt-1">Đã dùng {tokenPercent}% dung lượng</p>
                      </div>
                      <div className="text-xl font-black text-white">{tokenPercent}<span className="text-sm text-slate-400">%</span></div>
                    </div>
                    <div className="w-full bg-slate-800/50 rounded-full h-2 border border-white/10 overflow-hidden">
                      <div className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 h-full rounded-full" style={{ width: `${tokenPercent}%` }}></div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>

        {/* 
          ======== CÁC PANEL MỞ RỘNG (SLIDE-OVERS TỪ PHẢI) ======== 
        */}

        {/* Nền làm mờ nội dung phía sau nếu có Panel nào đó đang mở */}
        {activePanel !== 'none' && (
          <div
            onClick={() => setActivePanel('none')}
            className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px] z-20 cursor-pointer"
          />
        )}

        {/* 1. NOTIFICATION / PROPOSAL PANEL */}
        {activePanel === 'notif' && (
          <ProposalSidebar
            isOpen={true}
            onClose={() => setActivePanel('none')}
            proposals={proposals}
            onApprove={approveProposal}
            onDismiss={dismissProposal}
          />
        )}

        {/* 2. EMAIL PANEL */}
        {activePanel === 'email' && (
          <MailPanel isOpen={true} onClose={() => setActivePanel('none')} />
        )}

        {/* 3. CALENDAR PANEL */}
        {activePanel === 'calendar' && (
          <CalendarSidebar isOpen={true} onClose={() => setActivePanel('none')} />
        )}

        {/* 4. CHAT MÁY HỌC PANEL */}
        {activePanel === 'chat' && (
          <AgentChatPanel isOpen={true} onClose={() => setActivePanel('none')} chatState={chatState} />
        )}
      </div>

      <ConfigPanel isOpen={isConfigOpen} onClose={() => setIsConfigOpen(false)} />

      {/* Global CSS */}
      <style dangerouslySetInnerHTML={{
        __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 20px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: #94a3b8; }

        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .panel-slide-in {
          animation: slideInRight 0.3s ease-out forwards;
        }
      `}} />
    </div>
  );
}
