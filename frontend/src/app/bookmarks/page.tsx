'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { questionsAPI } from '@/lib/api';
import { Bookmark, Trash2 } from 'lucide-react';
import Link from 'next/link';

interface BookmarkItem {
    id: number;
    question: number;
    question_detail: {
        id: number;
        question_text: string;
        year: number;
        subject_name: string;
        topic_name: string;
        difficulty: string;
    };
    note: string;
    created_at: string;
}

export default function BookmarksPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            questionsAPI.getBookmarks()
                .then(res => setBookmarks(res.data.results || res.data || []))
                .catch(() => { })
                .finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    const removeBookmark = (questionId: number) => {
        questionsAPI.bookmark(questionId).then(() => {
            setBookmarks(prev => prev.filter(b => b.question !== questionId));
        });
    };

    const diffBadge = (d: string) => {
        const cls = d === 'easy' ? 'badge-easy' : d === 'hard' ? 'badge-hard' : 'badge-medium';
        return <span className={`badge ${cls}`}>{d}</span>;
    };

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
                    <Bookmark className="w-6 h-6" style={{ color: '#f59e0b' }} fill="#f59e0b" />
                    Bookmarks
                </h1>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                    Your saved questions for quick revision ({bookmarks.length} saved)
                </p>

                {loading ? (
                    <div className="glass-card p-8 text-center"><div className="animate-pulse gradient-text">Loading bookmarks...</div></div>
                ) : bookmarks.length === 0 ? (
                    <div className="glass-card p-12 text-center" style={{ color: 'var(--text-secondary)' }}>
                        <Bookmark className="w-12 h-12 mx-auto mb-4 opacity-30" />
                        <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>No bookmarks yet</h3>
                        <p className="text-sm mb-4">Bookmark questions from the Question Bank to save them for revision</p>
                        <Link href="/questions" className="btn-primary">Browse Questions</Link>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {bookmarks.map(b => (
                            <div key={b.id} className="glass-card p-4">
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="badge" style={{ background: 'rgba(139, 149, 168, 0.1)', color: 'var(--text-secondary)' }}>
                                            {b.question_detail.year} • {b.question_detail.subject_name}
                                        </span>
                                        {diffBadge(b.question_detail.difficulty)}
                                    </div>
                                    <button onClick={() => removeBookmark(b.question)}
                                        className="p-2 rounded-lg hover:bg-red-500/10" style={{ color: '#ef4444' }}>
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                                <Link href={`/questions?q=${b.question}`} className="text-sm leading-relaxed hover:underline">
                                    {b.question_detail.question_text}
                                </Link>
                                {b.question_detail.topic_name && (
                                    <span className="badge mt-2 block w-fit" style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-primary)', fontSize: '11px' }}>
                                        {b.question_detail.topic_name}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
