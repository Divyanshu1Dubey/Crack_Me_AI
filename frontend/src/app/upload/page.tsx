'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { aiAPI } from '@/lib/api';
import { Upload, Brain, FolderSearch, Database, FileText, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';

interface KnowledgeStats {
    total_chunks: number;
    books: Record<string, number>;
    indexed_files: number;
}

export default function UploadPage() {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const router = useRouter();
    const [stats, setStats] = useState<KnowledgeStats | null>(null);
    const [uploading, setUploading] = useState(false);
    const [scanning, setScanning] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [bookName, setBookName] = useState('');

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        } else if (!authLoading && user && user.role !== 'admin' && !user.is_admin) {
            // Non-admin users cannot access this page
            router.push('/dashboard');
        }
    }, [authLoading, isAuthenticated, user, router]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await aiAPI.getKnowledgeStats();
            setStats(res.data);
        } catch {
            // Stats might not be available yet
        }
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            const timer = setTimeout(() => fetchStats(), 0);
            return () => clearTimeout(timer);
        }
    }, [isAuthenticated, fetchStats]);

    const handleUpload = async () => {
        if (!selectedFile) return;
        setUploading(true);
        setMessage(null);
        try {
            const res = await aiAPI.uploadKnowledge(selectedFile, bookName || undefined);
            setMessage({
                type: res.data.status === 'success' ? 'success' : 'info',
                text: res.data.message || `Uploaded: ${res.data.chunks || 0} chunks`
            });
            setSelectedFile(null);
            setBookName('');
            fetchStats();
        } catch {
            setMessage({ type: 'error', text: 'Upload failed. Ensure file is PDF, MD, or TXT.' });
        }
        setUploading(false);
    };

    const handleScan = async () => {
        setScanning(true);
        setMessage(null);
        try {
            const res = await aiAPI.scanKnowledge();
            setMessage({
                type: 'success',
                text: res.data.message || `Scanned: ${res.data.new_files || 0} new files`
            });
            fetchStats();
        } catch {
            setMessage({ type: 'error', text: 'Scan failed.' });
        }
        setScanning(false);
    };

    if (authLoading) return null;

    return (
        <div className="min-h-screen flex bg-background">
            <Sidebar />
            <main className="flex-1 p-8 overflow-y-auto">
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center gap-3 mb-2">
                        <Database className="w-8 h-8" style={{ color: 'var(--accent-primary)' }} />
                        <h1 className="text-2xl font-bold">Knowledge Base & Upload</h1>
                    </div>
                    <p className="mb-8" style={{ color: 'var(--text-secondary)' }}>
                        Upload textbooks, notes, PDFs, or question papers to train the AI tutor
                    </p>

                    {/* Stats Cards */}
                    {stats && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                            <div className="glass-card p-5 text-center">
                                <div className="text-3xl font-bold gradient-text">{stats.total_chunks}</div>
                                <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Total Knowledge Chunks</div>
                            </div>
                            <div className="glass-card p-5 text-center">
                                <div className="text-3xl font-bold gradient-text">{Object.keys(stats.books || {}).length}</div>
                                <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Books Indexed</div>
                            </div>
                            <div className="glass-card p-5 text-center">
                                <div className="text-3xl font-bold gradient-text">{stats.indexed_files}</div>
                                <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Files Processed</div>
                            </div>
                        </div>
                    )}

                    {/* Message Banner */}
                    {message && (
                        <div className={`p-4 rounded-xl mb-6 flex items-center gap-3 ${message.type === 'success' ? 'bg-green-500/10 border border-green-500/30' :
                            message.type === 'error' ? 'bg-red-500/10 border border-red-500/30' :
                                'bg-blue-500/10 border border-blue-500/30'
                            }`}>
                            {message.type === 'success' ? <CheckCircle className="w-5 h-5 text-green-400" /> :
                                message.type === 'error' ? <AlertTriangle className="w-5 h-5 text-red-400" /> :
                                    <Brain className="w-5 h-5 text-blue-400" />}
                            <span>{message.text}</span>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        {/* Upload Card */}
                        <div className="glass-card p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Upload className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                <h2 className="text-lg font-bold">Upload New File</h2>
                            </div>
                            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                                Upload PDF, Markdown (.md), or Text (.txt) files. These will be indexed
                                into the AI knowledge base for grounded answers.
                            </p>

                            <div className="space-y-3">
                                <div>
                                    <label className="block text-sm font-medium mb-1">File (PDF / MD / TXT)</label>
                                    <input
                                        type="file"
                                        accept=".pdf,.md,.txt"
                                        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                        className="w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:font-semibold file:cursor-pointer"
                                        style={{ color: 'var(--text-secondary)' }}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Book Name (optional)</label>
                                    <input
                                        type="text"
                                        value={bookName}
                                        onChange={(e) => setBookName(e.target.value)}
                                        placeholder="e.g., Harrison's Medicine, My Surgery Notes"
                                        className="w-full px-3 py-2 rounded-lg border text-sm"
                                        style={{
                                            background: 'var(--bg-secondary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)'
                                        }}
                                    />
                                </div>
                                <button
                                    onClick={handleUpload}
                                    disabled={!selectedFile || uploading}
                                    className="btn-primary w-full justify-center gap-2"
                                >
                                    {uploading ? <><Loader2 className="w-4 h-4 animate-spin" /> Uploading &amp; Indexing...</> :
                                        <><Upload className="w-4 h-4" /> Upload &amp; Train</>}
                                </button>
                            </div>
                        </div>

                        {/* Auto-Scan Card */}
                        <div className="glass-card p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <FolderSearch className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                <h2 className="text-lg font-bold">Auto-Scan Files</h2>
                            </div>
                            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                                Scans the <code>Medura_Train/</code> directory for new or unindexed files
                                and automatically adds them to the AI knowledge base.
                            </p>
                            <div className="space-y-4">
                                <div className="p-3 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)' }}>
                                    <div className="font-semibold mb-2">📁 Where to put files:</div>
                                    <ul className="space-y-1" style={{ color: 'var(--text-secondary)' }}>
                                        <li>• <code>Medura_Train/textbooks/</code> — Textbook PDFs</li>
                                        <li>• <code>Medura_Train/PYQ/</code> — PYQ papers</li>
                                        <li>• <code>Medura_Train/web_knowledge/</code> — Notes, guides</li>
                                        <li>• <code>Medura_Train/uploads/</code> — Your uploads</li>
                                    </ul>
                                </div>
                                <button
                                    onClick={handleScan}
                                    disabled={scanning}
                                    className="btn-primary w-full justify-center gap-2"
                                >
                                    {scanning ? <><Loader2 className="w-4 h-4 animate-spin" /> Scanning...</> :
                                        <><FolderSearch className="w-4 h-4" /> Scan &amp; Index New Files</>}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Indexed Books Table */}
                    {stats && stats.books && Object.keys(stats.books).length > 0 && (
                        <div className="glass-card p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <FileText className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                <h2 className="text-lg font-bold">Indexed Books</h2>
                            </div>
                            <div className="space-y-2">
                                {Object.entries(stats.books).sort((a, b) => b[1] - a[1]).map(([book, chunks]) => (
                                    <div key={book} className="flex justify-between items-center p-3 rounded-lg"
                                        style={{ background: 'var(--bg-secondary)' }}>
                                        <span className="font-medium text-sm">{book}</span>
                                        <span className="text-xs px-2 py-1 rounded-full font-semibold"
                                            style={{ background: 'var(--accent-primary)', color: 'white' }}>
                                            {chunks} chunks
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Training Guide */}
                    <div className="glass-card p-6 mt-6">
                        <h2 className="text-lg font-bold mb-3">🧠 Training Guide</h2>
                        <div className="text-sm space-y-2" style={{ color: 'var(--text-secondary)' }}>
                            <p><strong>For large textbook PDFs</strong> (500+ pages), run the training script directly:</p>
                            <pre className="p-3 rounded-lg text-xs overflow-x-auto" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
{`cd backend
python train_on_colab.py`}
                            </pre>
                            <p>Or open <code>train_on_colab.py</code> in Google Colab if your machine crashes.</p>
                            <p className="mt-2"><strong>Supported formats:</strong> PDF, Markdown (.md), Plain Text (.txt)</p>
                            <p><strong>What gets indexed:</strong> Every page/section is split into ~500-word chunks, tokenized, and stored for TF-IDF retrieval. The AI tutor uses these chunks to ground its answers with citations.</p>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
