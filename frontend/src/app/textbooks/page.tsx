'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { textbooksAPI } from '@/lib/api';
import { BookOpen, Upload, Search, ExternalLink, FileText, Loader2 } from 'lucide-react';

interface Textbook {
    id: number;
    name: string;
    author: string;
    edition: string;
    subject: number;
    subject_name?: string;
    description: string;
    cover_image?: string;
    chapters?: { id: number; number: number; title: string }[];
}

interface PDFUpload {
    id: number;
    title: string;
    file: string;
    is_processed: boolean;
    uploaded_at: string;
}

export default function TextbooksPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [textbooks, setTextbooks] = useState<Textbook[]>([]);
    const [uploads, setUploads] = useState<PDFUpload[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState<'library' | 'uploads'>('library');
    const [uploading, setUploading] = useState(false);
    const [expandedBook, setExpandedBook] = useState<number | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                textbooksAPI.list().catch(() => ({ data: { results: [] } })),
                textbooksAPI.getUploads().catch(() => ({ data: { results: [] } })),
            ]).then(([bRes, uRes]) => {
                setTextbooks(bRes.data?.results || bRes.data || []);
                setUploads(uRes.data?.results || uRes.data || []);
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('title', file.name.replace(/\.[^.]+$/, ''));
            const res = await textbooksAPI.upload(formData);
            setUploads(prev => [res.data, ...prev]);
        } catch {
            // Error handled silently
        } finally {
            setUploading(false);
        }
    };

    const filtered = textbooks.filter(b =>
        b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        b.author.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Standard CMS textbook recommendations when library is empty
    const recommendedBooks = [
        { name: "Harrison's Principles of Internal Medicine", author: 'Kasper, Fauci et al.', subject: 'General Medicine', color: '#06b6d4' },
        { name: "Essential Pediatrics (O.P. Ghai)", author: 'O.P. Ghai', subject: 'Pediatrics', color: '#8b5cf6' },
        { name: "Park's Textbook of PSM", author: 'K. Park', subject: 'Preventive & Social Medicine', color: '#10b981' },
        { name: "SRB's Manual of Surgery", author: 'Sriram Bhat M.', subject: 'Surgery', color: '#f59e0b' },
        { name: "DC Dutta's Textbook of Obstetrics", author: 'Hiralal Konar', subject: 'OBG', color: '#ec4899' },
        { name: "Robbins Pathologic Basis of Disease", author: 'Kumar, Abbas, Aster', subject: 'Pathology', color: '#ef4444' },
        { name: "KD Tripathi's Pharmacology", author: 'KD Tripathi', subject: 'Pharmacology', color: '#14b8a6' },
        { name: "Guyton & Hall Medical Physiology", author: 'John E. Hall', subject: 'Physiology', color: '#a855f7' },
        { name: "Harper's Illustrated Biochemistry", author: 'Murray, Bender et al.', subject: 'Biochemistry', color: '#f97316' },
        { name: "Gray's Anatomy", author: 'Susan Standring', subject: 'Anatomy', color: '#64748b' },
        { name: "Jawetz Medical Microbiology", author: 'Brooks, Carroll et al.', subject: 'Microbiology', color: '#22d3ee' },
        { name: "Khurana Ophthalmology", author: 'A.K. Khurana', subject: 'Ophthalmology', color: '#e879f9' },
    ];

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <BookOpen className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                            Textbooks & References
                        </h1>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            Standard textbooks and your uploaded study materials
                        </p>
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 mb-6">
                    <button onClick={() => setActiveTab('library')}
                        className={`px-5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${activeTab === 'library' ? 'btn-primary' : 'btn-secondary'}`}>
                        <BookOpen className="w-4 h-4" /> Library
                    </button>
                    <button onClick={() => setActiveTab('uploads')}
                        className={`px-5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${activeTab === 'uploads' ? 'btn-primary' : 'btn-secondary'}`}>
                        <Upload className="w-4 h-4" /> My Uploads ({uploads.length})
                    </button>
                </div>

                {activeTab === 'library' ? (
                    <>
                        {/* Search */}
                        <div className="relative mb-6">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                            <input
                                className="input-field pl-10 w-full"
                                placeholder="Search textbooks..."
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                            />
                        </div>

                        {loading ? (
                            <div className="glass-card p-12 text-center">
                                <Loader2 className="w-8 h-8 mx-auto animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                <p className="text-sm mt-3" style={{ color: 'var(--text-secondary)' }}>Loading textbooks...</p>
                            </div>
                        ) : filtered.length > 0 ? (
                            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {filtered.map(book => (
                                    <div key={book.id} className="glass-card p-5 cursor-pointer transition-all hover:scale-[1.01]"
                                        onClick={() => setExpandedBook(expandedBook === book.id ? null : book.id)}>
                                        <div className="flex items-start gap-3 mb-3">
                                            <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                                                style={{ background: 'rgba(6,182,212,0.1)' }}>
                                                <BookOpen className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                                            </div>
                                            <div className="min-w-0">
                                                <h3 className="font-bold text-sm leading-tight">{book.name}</h3>
                                                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{book.author}</p>
                                                {book.edition && <span className="badge text-xs mt-1">{book.edition}</span>}
                                            </div>
                                        </div>
                                        {book.description && (
                                            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{book.description}</p>
                                        )}
                                        {expandedBook === book.id && book.chapters && book.chapters.length > 0 && (
                                            <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(139,149,168,0.1)' }}>
                                                <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>Chapters:</div>
                                                <div className="space-y-1">
                                                    {book.chapters.map(ch => (
                                                        <div key={ch.id} className="text-xs py-1" style={{ color: 'var(--text-secondary)' }}>
                                                            Ch.{ch.number}: {ch.title}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            // Show recommended books when library is empty
                            <div>
                                <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                                    Recommended standard textbooks for UPSC CMS preparation:
                                </p>
                                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {recommendedBooks.map((book, i) => (
                                        <div key={i} className="glass-card p-5">
                                            <div className="flex items-start gap-3">
                                                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                                                    style={{ background: `${book.color}15`, color: book.color }}>
                                                    <BookOpen className="w-6 h-6" />
                                                </div>
                                                <div>
                                                    <h3 className="font-bold text-sm leading-tight">{book.name}</h3>
                                                    <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{book.author}</p>
                                                    <span className="badge text-xs mt-2" style={{ background: `${book.color}10`, color: book.color }}>
                                                        {book.subject}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    // Uploads Tab
                    <div>
                        <div className="glass-card p-6 mb-6 text-center" style={{
                            border: '2px dashed rgba(139,149,168,0.2)',
                            background: 'rgba(6,182,212,0.03)',
                        }}>
                            <Upload className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--accent-primary)', opacity: 0.5 }} />
                            <p className="text-sm font-medium mb-2">Upload your study materials</p>
                            <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
                                PDF notes, handwritten scans, or study guides
                            </p>
                            <label className="btn-primary inline-flex cursor-pointer">
                                <Upload className="w-4 h-4" />
                                {uploading ? 'Uploading...' : 'Choose File'}
                                <input type="file" accept=".pdf,.doc,.docx,.txt,.md" className="hidden" onChange={handleUpload} disabled={uploading} />
                            </label>
                        </div>

                        {uploads.length === 0 ? (
                            <div className="glass-card p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
                                <FileText className="w-12 h-12 mx-auto mb-4 opacity-30" />
                                <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>No uploads yet</h3>
                                <p className="text-sm">Upload your PDF notes and study materials to access them here</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {uploads.map(u => (
                                    <div key={u.id} className="glass-card p-4 flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                                            style={{ background: 'rgba(245,158,11,0.1)' }}>
                                            <FileText className="w-5 h-5" style={{ color: '#f59e0b' }} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-medium text-sm truncate">{u.title}</h4>
                                            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                Uploaded {new Date(u.uploaded_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className={`badge text-xs ${u.is_processed ? '' : ''}`} style={{
                                                background: u.is_processed ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                                                color: u.is_processed ? '#10b981' : '#f59e0b',
                                            }}>
                                                {u.is_processed ? 'Indexed' : 'Pending'}
                                            </span>
                                            {u.file && (
                                                <a href={u.file} target="_blank" rel="noopener noreferrer"
                                                    className="p-2 rounded-lg hover:bg-white/5">
                                                    <ExternalLink className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
