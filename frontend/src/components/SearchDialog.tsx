'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import { Search, BookOpen, X, Loader2, FileText, Brain, Layers, BarChart, GraduationCap, Settings } from 'lucide-react';

interface SearchResult {
    id: number;
    question_text: string;
    year: number;
    subject_name: string;
    topic_name: string;
    difficulty: string;
}

export default function SearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
    const router = useRouter();
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<SearchResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    const handleClose = useCallback(() => {
        setQuery('');
        setResults([]);
        setSelectedIndex(0);
        onClose();
    }, [onClose]);

    useEffect(() => {
        if (open) {
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [open]);

    const searchQuestions = useCallback((q: string) => {
        if (q.length < 2) { setResults([]); return; }
        setLoading(true);
        questionsAPI.list({ search: q, page_size: 8 }).then(res => {
            const data = res.data;
            setResults(data.results || data || []);
            setSelectedIndex(0);
        }).catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, []);

    const handleInputChange = (value: string) => {
        setQuery(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => searchQuestions(value), 300);
    };

    const handleSelect = (id: number) => {
        handleClose();
        router.push(`/questions?q=${id}`);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(prev => Math.min(prev + 1, totalItems - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(prev => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter') {
            if (showActions && actions[selectedIndex]) {
                handleActionSelect(actions[selectedIndex].path);
            } else if (results[selectedIndex]) {
                handleSelect(results[selectedIndex].id);
            }
        } else if (e.key === 'Escape') {
            handleClose();
        }
    };

    // Strip markdown for preview
    const strip = (text: string) => text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*+/g, '').replace(/#+\s?/g, '').trim();

    // Quick actions shown when query is empty
    const actions = [
        { label: 'Start Practice Test', icon: FileText, path: '/tests' },
        { label: 'Open AI Tutor', icon: Brain, path: '/ai-tutor' },
        { label: 'Create Flashcard', icon: Layers, path: '/flashcards' },
        { label: 'View Analytics', icon: BarChart, path: '/analytics' },
        { label: 'Study Plan', icon: GraduationCap, path: '/ai-tutor?mode=study-plan' },
        { label: 'Admin Panel', icon: Settings, path: '/admin' },
    ];

    const handleActionSelect = (path: string) => {
        handleClose();
        router.push(path);
    };

    // Combined items for keyboard navigation: actions (when no query) or results (when querying)
    const showActions = query.length < 2 && results.length === 0;
    const totalItems = showActions ? actions.length : results.length;

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]" onClick={handleClose}>
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
            <div className="relative w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden"
                onClick={e => e.stopPropagation()}>
                {/* Search Input */}
                <div className="flex items-center gap-3 px-4 border-b border-border">
                    <Search className="w-5 h-5 text-muted-foreground shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        className="flex-1 py-4 bg-transparent text-foreground text-sm outline-none placeholder:text-muted-foreground"
                        placeholder="Search questions, topics, concepts..."
                        value={query}
                        onChange={e => handleInputChange(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                    {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
                    <button onClick={handleClose} className="p-1 rounded hover:bg-accent">
                        <X className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>

                {/* Results */}
                {results.length > 0 && (
                    <div className="max-h-[320px] overflow-y-auto p-2">
                        {results.map((r, i) => (
                            <button
                                key={r.id}
                                className={`w-full text-left px-3 py-2.5 rounded-lg flex items-start gap-3 transition-colors ${i === selectedIndex ? 'bg-accent' : 'hover:bg-accent/50'}`}
                                onClick={() => handleSelect(r.id)}
                                onMouseEnter={() => setSelectedIndex(i)}
                            >
                                <BookOpen className="w-4 h-4 mt-0.5 shrink-0 text-primary" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm leading-snug line-clamp-2 text-foreground">{strip(r.question_text)}</p>
                                    <div className="flex gap-2 mt-1">
                                        <span className="text-[10px] text-muted-foreground">{r.year}</span>
                                        <span className="text-[10px] text-muted-foreground">{r.subject_name}</span>
                                        {r.topic_name && <span className="text-[10px] text-muted-foreground">{r.topic_name}</span>}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}

                {/* Quick Actions — shown when query is empty */}
                {showActions && !loading && (
                    <div className="p-2">
                        <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Quick Actions</p>
                        {actions.map((action, i) => (
                            <button
                                key={action.path}
                                className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-3 transition-colors ${i === selectedIndex ? 'bg-accent' : 'hover:bg-accent/50'}`}
                                onClick={() => handleActionSelect(action.path)}
                                onMouseEnter={() => setSelectedIndex(i)}
                            >
                                <action.icon className="w-4 h-4 shrink-0 text-primary" />
                                <span className="text-sm text-foreground">{action.label}</span>
                            </button>
                        ))}
                    </div>
                )}

                {/* Empty search state */}
                {query.length >= 2 && !loading && results.length === 0 && (
                    <div className="p-6 text-center text-sm text-muted-foreground">
                        No questions found for &quot;{query}&quot;
                    </div>
                )}

                {/* Footer */}
                <div className="px-4 py-2 border-t border-border flex items-center gap-4 text-[10px] text-muted-foreground">
                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">↑↓</kbd> navigate</span>
                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">↵</kbd> select</span>
                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">esc</kbd> close</span>
                </div>
            </div>
        </div>
    );
}
