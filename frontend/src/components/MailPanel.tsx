"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  Mail, X, RotateCw, ChevronLeft, ChevronDown,
  Send, Trash2, MailOpen, Star, Reply,
} from 'lucide-react';
import {
  fetchEmails, fetchEmailDetail, markEmailRead, trashEmail, replyToEmail,
  getLinkedAccounts,
  type EmailItem, type EmailDetail, type LinkedAccount,
} from '@/lib/api';

interface MailPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

// Helper: parse "Nguyễn Văn A <a@gmail.com>" → "Nguyễn Văn A"
function parseSenderName(from: string): string {
  const match = from.match(/^"?(.+?)"?\s*<.*>$/);
  return match ? match[1] : from.split('@')[0];
}

// Helper: relative time
function relativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'Vừa xong';
    if (diff < 3600) return `${Math.floor(diff / 60)} phút`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} giờ`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} ngày`;
    return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
  } catch { return dateStr; }
}

// === Module-level cache — tồn tại qua các lần mở/đóng panel ===
const CACHE_TTL = 5 * 60 * 1000; // 5 phút
const _emailCache: Record<string, { data: EmailItem[]; ts: number }> = {};
const _detailCache: Record<string, { data: EmailDetail; ts: number }> = {};

function getCacheKey(filter: string) { return filter || '__all__'; }

export default function MailPanel({ isOpen, onClose }: MailPanelProps) {
  // === State ===
  const [view, setView] = useState<'list' | 'detail' | 'reply'>('list');
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState<EmailDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filter
  const [accounts, setAccounts] = useState<LinkedAccount[]>([]);
  const [filterEmail, setFilterEmail] = useState<string>('');
  const [filterOpen, setFilterOpen] = useState(false);

  // Reply
  const [replyText, setReplyText] = useState('');
  const [replySending, setReplySending] = useState(false);

  // === Load accounts (có cache) ===
  useEffect(() => {
    if (!isOpen || accounts.length > 0) return;
    getLinkedAccounts().then(d => setAccounts(d.accounts || [])).catch(() => {});
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // === Load emails (with cache) ===
  const loadEmails = useCallback(async (force = false) => {
    const key = getCacheKey(filterEmail);
    const cached = _emailCache[key];

    // Trả cache nếu còn hạn + không force refresh
    if (!force && cached && (Date.now() - cached.ts) < CACHE_TTL) {
      setEmails(cached.data);
      return;
    }

    setLoading(true);
    try {
      const data = await fetchEmails({
        account_email: filterEmail || undefined,
        limit: 30,
      });
      const list = data.emails || [];
      setEmails(list);
      _emailCache[key] = { data: list, ts: Date.now() };
    } catch { setEmails([]); }
    setLoading(false);
  }, [filterEmail]);

  useEffect(() => {
    if (isOpen) loadEmails();
  }, [isOpen, loadEmails]);


  // === Handlers ===
  const handleOpenEmail = async (email: EmailItem) => {
    setDetailLoading(true);
    setView('detail');
    try {
      // Check detail cache
      const cacheKey = `${email.account_email}:${email.id}`;
      const cached = _detailCache[cacheKey];
      let detail: EmailDetail;

      if (cached && (Date.now() - cached.ts) < CACHE_TTL) {
        detail = cached.data;
      } else {
        const data = await fetchEmailDetail(email.id, email.account_email);
        detail = data.email;
        _detailCache[cacheKey] = { data: detail, ts: Date.now() };
      }

      setSelectedEmail(detail);

      // Mark as read
      if (email.is_unread) {
        await markEmailRead(email.id, email.account_email);
        setEmails(prev => {
          const updated = prev.map(e => e.id === email.id ? { ...e, is_unread: false } : e);
          // Sync list cache
          const key = getCacheKey(filterEmail);
          _emailCache[key] = { data: updated, ts: Date.now() };
          return updated;
        });
      }
    } catch { setSelectedEmail(null); }
    setDetailLoading(false);
  };

  const handleTrash = async () => {
    if (!selectedEmail) return;
    try {
      await trashEmail(selectedEmail.id, selectedEmail.account_email);
      setEmails(prev => {
        const updated = prev.filter(e => e.id !== selectedEmail.id);
        // Invalidate list cache
        const key = getCacheKey(filterEmail);
        _emailCache[key] = { data: updated, ts: Date.now() };
        return updated;
      });
      // Remove detail cache
      delete _detailCache[`${selectedEmail.account_email}:${selectedEmail.id}`];
      setView('list');
      setSelectedEmail(null);
    } catch (e) { console.error('Trash error:', e); }
  };

  const handleReply = () => {
    setReplyText('');
    setView('reply');
  };

  const handleSendReply = async () => {
    if (!selectedEmail || !replyText.trim()) return;
    setReplySending(true);
    try {
      await replyToEmail(selectedEmail.id, replyText, selectedEmail.account_email);
      setView('detail');
      setReplyText('');
    } catch (e) { console.error('Reply error:', e); }
    setReplySending(false);
  };

  const handleBack = () => {
    if (view === 'reply') { setView('detail'); return; }
    setView('list');
    setSelectedEmail(null);
  };

  // === RENDER ===
  return (
    <div className={`absolute top-0 right-0 h-full w-[420px] bg-white shadow-2xl border-l border-slate-200 z-30 flex flex-col transition-transform duration-300 ease-in-out ${isOpen ? "translate-x-0" : "translate-x-full"}`}>

      {/* ───── HEADER ───── */}
      <div className="flex justify-between items-center bg-slate-50 border-b border-slate-100 p-4 shrink-0">
        <div className="flex items-center gap-2">
          {view !== 'list' && (
            <button onClick={handleBack} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}
          <h2 className="font-bold text-slate-800 flex items-center gap-2 text-[15px]">
            <Mail className="w-4 h-4 text-indigo-500" />
            {view === 'list' ? 'Hộp Thư' : view === 'reply' ? 'Trả lời' : (selectedEmail?.subject || 'Chi tiết')}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          {view === 'list' && (
            <button onClick={() => loadEmails(true)} disabled={loading} className="p-2 text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 rounded-xl transition-colors">
              <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200 bg-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ───── FILTER BAR (list only) ───── */}
      {view === 'list' && accounts.length > 1 && (
        <div className="px-4 py-2.5 border-b border-slate-100 bg-white relative">
          <button
            onClick={() => setFilterOpen(!filterOpen)}
            className="flex items-center gap-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg transition-colors w-full justify-between"
          >
            <span className="truncate">{filterEmail || 'Tất cả tài khoản'}</span>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${filterOpen ? 'rotate-180' : ''}`} />
          </button>
          {filterOpen && (
            <div className="absolute top-full left-4 right-4 bg-white border border-slate-200 rounded-xl shadow-xl z-50 mt-1 overflow-hidden">
              <button
                onClick={() => { setFilterEmail(''); setFilterOpen(false); }}
                className={`w-full text-left px-4 py-2.5 text-xs font-medium hover:bg-indigo-50 transition-colors ${!filterEmail ? 'text-indigo-600 bg-indigo-50/50' : 'text-slate-600'}`}
              >
                📬 Tất cả tài khoản
              </button>
              {accounts.map(acc => (
                <button
                  key={acc.id}
                  onClick={() => { setFilterEmail(acc.email); setFilterOpen(false); }}
                  className={`w-full text-left px-4 py-2.5 text-xs font-medium hover:bg-indigo-50 transition-colors border-t border-slate-50 ${filterEmail === acc.email ? 'text-indigo-600 bg-indigo-50/50' : 'text-slate-600'}`}
                >
                  <Mail className="w-3 h-3 inline mr-2 text-slate-400" />{acc.email}
                  {acc.is_primary && <span className="ml-1 text-[10px] text-indigo-400">(Primary)</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ───── EMAIL LIST ───── */}
      {view === 'list' && (
        <div className="flex-1 overflow-y-auto bg-slate-50/50">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <RotateCw className="w-6 h-6 text-indigo-400 animate-spin" />
              <span className="text-sm text-slate-400 font-medium">Đang tải email...</span>
            </div>
          ) : emails.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <Mail className="w-12 h-12 text-slate-200" />
              <span className="text-sm text-slate-400">Không có email nào</span>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {emails.map(email => (
                <button
                  key={`${email.account_email}-${email.id}`}
                  onClick={() => handleOpenEmail(email)}
                  className={`w-full text-left px-4 py-3.5 hover:bg-indigo-50/50 transition-colors ${email.is_unread ? 'bg-white' : 'bg-slate-50/30'}`}
                >
                  <div className="flex justify-between items-start gap-2 mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      {email.is_unread && <div className="w-2 h-2 bg-indigo-500 rounded-full shrink-0" />}
                      {email.is_starred && <Star className="w-3 h-3 text-amber-400 fill-amber-400 shrink-0" />}
                      <span className={`text-[13px] truncate ${email.is_unread ? 'font-bold text-slate-900' : 'font-medium text-slate-600'}`}>
                        {parseSenderName(email.from)}
                      </span>
                    </div>
                    <span className="text-[10px] font-medium text-slate-400 shrink-0 whitespace-nowrap">
                      {relativeTime(email.date)}
                    </span>
                  </div>
                  <p className={`text-[12px] truncate ${email.is_unread ? 'font-semibold text-slate-800' : 'text-slate-600'}`}>
                    {email.subject || '(Không có tiêu đề)'}
                  </p>
                  <p className="text-[11px] text-slate-400 truncate mt-0.5 leading-relaxed">
                    {email.snippet}
                  </p>
                  {accounts.length > 1 && email.account_email && (
                    <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-wider mt-1 inline-block">
                      {email.account_email.split('@')[0]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ───── EMAIL DETAIL ───── */}
      {view === 'detail' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {detailLoading || !selectedEmail ? (
            <div className="flex-1 flex items-center justify-center">
              <RotateCw className="w-6 h-6 text-indigo-400 animate-spin" />
            </div>
          ) : (
            <>
              {/* Meta */}
              <div className="p-4 border-b border-slate-100 bg-white shrink-0 space-y-2">
                <h3 className="text-[15px] font-bold text-slate-800 leading-snug">{selectedEmail.subject}</h3>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                    <span className="text-xs font-bold text-indigo-600">
                      {parseSenderName(selectedEmail.from).charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold text-slate-700 truncate">{parseSenderName(selectedEmail.from)}</p>
                    <p className="text-[10px] text-slate-400 truncate">Đến: {selectedEmail.to}</p>
                  </div>
                  <span className="ml-auto text-[10px] text-slate-400 shrink-0">{relativeTime(selectedEmail.date)}</span>
                </div>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto p-4 bg-white">
                <div
                  className="text-[13px] text-slate-700 leading-relaxed whitespace-pre-wrap break-words"
                  dangerouslySetInnerHTML={{ __html: selectedEmail.body.replace(/\n/g, '<br/>') }}
                />
              </div>

              {/* Action Bar */}
              <div className="flex items-center gap-2 p-3 border-t border-slate-100 bg-slate-50 shrink-0">
                <button onClick={handleReply} className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-indigo-500 text-white rounded-xl text-xs font-bold hover:bg-indigo-600 transition-colors shadow-sm">
                  <Reply className="w-3.5 h-3.5" /> Trả lời
                </button>
                <button
                  onClick={async () => {
                    if (selectedEmail.is_unread) {
                      await markEmailRead(selectedEmail.id, selectedEmail.account_email);
                      setEmails(prev => prev.map(e => e.id === selectedEmail.id ? { ...e, is_unread: false } : e));
                      setSelectedEmail({ ...selectedEmail, is_unread: false });
                    }
                  }}
                  className="p-2.5 text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 rounded-xl transition-colors border border-slate-200 bg-white"
                  title="Đánh dấu đã đọc"
                >
                  <MailOpen className="w-4 h-4" />
                </button>
                <button onClick={handleTrash} className="p-2.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors border border-slate-200 bg-white" title="Xoá">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* ───── REPLY VIEW ───── */}
      {view === 'reply' && selectedEmail && (
        <div className="flex-1 flex flex-col">
          <div className="p-4 border-b border-slate-100 bg-white shrink-0">
            <p className="text-xs text-slate-400 mb-1">Trả lời cho:</p>
            <p className="text-[13px] font-semibold text-slate-700 truncate">{selectedEmail.from}</p>
            <p className="text-[12px] text-slate-500 mt-1">Re: {selectedEmail.subject}</p>
          </div>
          <div className="flex-1 p-4">
            <textarea
              value={replyText}
              onChange={e => setReplyText(e.target.value)}
              placeholder="Nhập nội dung trả lời..."
              className="w-full h-full resize-none border border-slate-200 rounded-xl p-4 text-[13px] text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 placeholder:text-slate-300"
              autoFocus
            />
          </div>
          <div className="p-3 border-t border-slate-100 bg-slate-50 shrink-0">
            <button
              onClick={handleSendReply}
              disabled={replySending || !replyText.trim()}
              className="w-full flex items-center justify-center gap-2 py-3 bg-indigo-500 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              {replySending ? <RotateCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {replySending ? 'Đang gửi...' : 'Gửi trả lời'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
