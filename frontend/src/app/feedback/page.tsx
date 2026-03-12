'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';
import { MessageSquare, Send, Star, CheckCircle, Clock, Reply, Trash2, Download } from 'lucide-react';

interface FeedbackItem {
    id: number;
    username: string;
    category: string;
    rating: number;
    title: string;
    message: string;
    is_read: boolean;
    admin_reply: string;
    created_at: string;
}

const CATEGORIES = [
    { value: 'general', label: 'General Feedback' },
    { value: 'bug', label: 'Bug Report' },
    { value: 'feature', label: 'Feature Request' },
    { value: 'content', label: 'Content Issue' },
    { value: 'ui', label: 'UI/UX Feedback' },
    { value: 'ai', label: 'AI Quality' },
];

const categoryColor: Record<string, string> = {
    bug: '#ef4444', feature: '#8b5cf6', content: '#f59e0b',
    ui: '#06b6d4', ai: '#10b981', general: '#6b7280',
};

export default function FeedbackPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [success, setSuccess] = useState(false);
    const [replyingTo, setReplyingTo] = useState<number | null>(null);
    const [replyText, setReplyText] = useState('');

    // Form state
    const [category, setCategory] = useState('general');
    const [rating, setRating] = useState(5);
    const [title, setTitle] = useState('');
    const [message, setMessage] = useState('');

    const isAdmin = (user as any)?.is_admin;

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) loadFeedback();
    }, [authLoading, isAuthenticated, router]);

    const loadFeedback = () => {
        analyticsAPI.getFeedback()
            .then(res => setFeedbacks(res.data.results || res.data || []))
            .catch(() => {})
            .finally(() => setLoading(false));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!title.trim() || !message.trim()) return;
        setSubmitting(true);
        analyticsAPI.submitFeedback({ category, rating, title: title.trim(), message: message.trim() })
            .then(() => {
                setSuccess(true);
                setTitle(''); setMessage(''); setCategory('general'); setRating(5);
                loadFeedback();
                setTimeout(() => setSuccess(false), 3000);
            })
            .catch(() => {})
            .finally(() => setSubmitting(false));
    };

    const handleReply = (id: number) => {
        if (!replyText.trim()) return;
        analyticsAPI.replyFeedback(id, { admin_reply: replyText.trim() })
            .then(() => { setReplyingTo(null); setReplyText(''); loadFeedback(); })
            .catch(() => {});
    };

    const handleDelete = (id: number) => {
        analyticsAPI.deleteFeedback(id).then(() => loadFeedback()).catch(() => {});
    };

    const downloadCSV = (type: string) => {
        analyticsAPI.exportCSV(type)
            .then(res => {
                const blob = new Blob([res.data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `crackcms_${type}.csv`;
                a.click();
                window.URL.revokeObjectURL(url);
            })
            .catch(() => {});
    };

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
                    <MessageSquare className="w-6 h-6" style={{ color: '#8b5cf6' }} />
                    {isAdmin ? 'Student Feedback' : 'Send Feedback'}
                </h1>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                    {isAdmin ? 'View and reply to all student feedback' : 'Help us improve CrackCMS — your feedback matters!'}
                </p>

                {/* Admin Download Buttons */}
                {isAdmin && (
                    <div className="glass-card p-4 mb-6">
                        <h3 className="text-sm font-bold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                            <Download className="w-4 h-4" /> Download Data as CSV
                        </h3>
                        <div className="flex flex-wrap gap-2">
                            {[
                                { type: 'users', label: 'Users' },
                                { type: 'tokens', label: 'Token Balances' },
                                { type: 'transactions', label: 'Transactions' },
                                { type: 'feedback', label: 'Feedback' },
                            ].map(item => (
                                <button key={item.type} onClick={() => downloadCSV(item.type)}
                                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
                                    style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
                                    <Download className="w-3.5 h-3.5" /> {item.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Submit Form (students) */}
                {!isAdmin && (
                    <form onSubmit={handleSubmit} className="glass-card p-6 mb-8">
                        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                            Share Your Feedback
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div>
                                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Category</label>
                                <select value={category} onChange={e => setCategory(e.target.value)}
                                    className="w-full p-2.5 rounded-lg border"
                                    style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', borderColor: 'var(--border-color)' }}>
                                    {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Rating</label>
                                <div className="flex gap-1 mt-1">
                                    {[1, 2, 3, 4, 5].map(s => (
                                        <button key={s} type="button" onClick={() => setRating(s)}
                                            className="transition-transform hover:scale-110">
                                            <Star className="w-7 h-7" fill={s <= rating ? '#f59e0b' : 'transparent'}
                                                stroke={s <= rating ? '#f59e0b' : 'var(--text-muted)'} />
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="mb-4">
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Title</label>
                            <input value={title} onChange={e => setTitle(e.target.value)}
                                placeholder="Brief summary of your feedback"
                                className="w-full p-2.5 rounded-lg border"
                                style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', borderColor: 'var(--border-color)' }}
                                maxLength={200} required />
                        </div>

                        <div className="mb-4">
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Message</label>
                            <textarea value={message} onChange={e => setMessage(e.target.value)}
                                placeholder="Tell us more about your experience, suggestion, or issue..."
                                rows={4} className="w-full p-2.5 rounded-lg border resize-none"
                                style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', borderColor: 'var(--border-color)' }}
                                required />
                        </div>

                        <button type="submit" disabled={submitting || !title.trim() || !message.trim()}
                            className="flex items-center gap-2 px-6 py-2.5 rounded-lg font-bold text-white transition-all hover:scale-[1.02] disabled:opacity-50"
                            style={{ background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)' }}>
                            <Send className="w-4 h-4" />
                            {submitting ? 'Sending...' : 'Submit Feedback'}
                        </button>

                        {success && (
                            <div className="mt-3 flex items-center gap-2 text-sm font-medium" style={{ color: '#10b981' }}>
                                <CheckCircle className="w-4 h-4" /> Feedback submitted successfully! Thank you.
                            </div>
                        )}
                    </form>
                )}

                {/* Feedback List */}
                <div>
                    <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                        {isAdmin ? `All Feedback (${feedbacks.length})` : 'Your Previous Feedback'}
                    </h2>

                    {loading ? (
                        <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Loading...</div>
                    ) : feedbacks.length === 0 ? (
                        <div className="glass-card p-8 text-center" style={{ color: 'var(--text-muted)' }}>
                            {isAdmin ? 'No feedback received yet.' : 'You haven\'t submitted any feedback yet.'}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {feedbacks.map(fb => (
                                <div key={fb.id} className="glass-card p-5">
                                    <div className="flex items-start justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                            <span className="text-xs px-2 py-0.5 rounded-full font-bold text-white"
                                                style={{ background: categoryColor[fb.category] || '#6b7280' }}>
                                                {CATEGORIES.find(c => c.value === fb.category)?.label || fb.category}
                                            </span>
                                            {isAdmin && (
                                                <span className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>
                                                    @{fb.username}
                                                </span>
                                            )}
                                            <div className="flex">
                                                {[1, 2, 3, 4, 5].map(s => (
                                                    <Star key={s} className="w-3.5 h-3.5"
                                                        fill={s <= fb.rating ? '#f59e0b' : 'transparent'}
                                                        stroke={s <= fb.rating ? '#f59e0b' : 'var(--text-muted)'} />
                                                ))}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {fb.is_read ? (
                                                <span className="text-xs flex items-center gap-1" style={{ color: '#10b981' }}>
                                                    <CheckCircle className="w-3 h-3" /> Read
                                                </span>
                                            ) : (
                                                <span className="text-xs flex items-center gap-1" style={{ color: '#f59e0b' }}>
                                                    <Clock className="w-3 h-3" /> Pending
                                                </span>
                                            )}
                                            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                                {new Date(fb.created_at).toLocaleDateString()}
                                            </span>
                                        </div>
                                    </div>

                                    <h3 className="font-bold mb-1" style={{ color: 'var(--text-primary)' }}>{fb.title}</h3>
                                    <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>{fb.message}</p>

                                    {fb.admin_reply && (
                                        <div className="p-3 rounded-lg mt-2" style={{ background: 'rgba(139,92,246,0.08)', borderLeft: '3px solid #8b5cf6' }}>
                                            <p className="text-xs font-bold mb-1" style={{ color: '#8b5cf6' }}>Admin Reply</p>
                                            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{fb.admin_reply}</p>
                                        </div>
                                    )}

                                    {/* Admin actions */}
                                    {isAdmin && (
                                        <div className="flex items-center gap-2 mt-3">
                                            <button onClick={() => { setReplyingTo(replyingTo === fb.id ? null : fb.id); setReplyText(fb.admin_reply || ''); }}
                                                className="text-xs flex items-center gap-1 px-3 py-1 rounded-lg transition-colors"
                                                style={{ background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>
                                                <Reply className="w-3 h-3" /> Reply
                                            </button>
                                            <button onClick={() => handleDelete(fb.id)}
                                                className="text-xs flex items-center gap-1 px-3 py-1 rounded-lg transition-colors"
                                                style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
                                                <Trash2 className="w-3 h-3" /> Delete
                                            </button>
                                        </div>
                                    )}

                                    {/* Reply form */}
                                    {isAdmin && replyingTo === fb.id && (
                                        <div className="mt-3 flex gap-2">
                                            <input value={replyText} onChange={e => setReplyText(e.target.value)}
                                                placeholder="Type your reply..."
                                                className="flex-1 p-2 text-sm rounded-lg border"
                                                style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', borderColor: 'var(--border-color)' }} />
                                            <button onClick={() => handleReply(fb.id)}
                                                className="px-4 py-2 rounded-lg text-sm font-bold text-white"
                                                style={{ background: '#8b5cf6' }}>
                                                Send
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
                </div>
            </div>
        </div>
    );
}
