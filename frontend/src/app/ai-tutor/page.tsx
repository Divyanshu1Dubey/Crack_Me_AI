/**
 * ai-tutor/page.tsx — AI Medical Tutor chat interface.
 * Real-time chat with Gemini/Groq AI for CMS exam preparation.
 * Features: suggested starter prompts, markdown-rendered responses,
 * chat history sidebar, auto-scroll to AI answer top, token consumption with 429 handling.
 */
'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { aiAPI, extractApiErrorMessage } from '@/lib/api';
import { Brain, Send, Sparkles, BookOpen, Lightbulb, Bot, User, Loader2, Search, FileText, ChevronDown, History, Plus, Trash2, X, MessageSquare, Clock } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Message {
    role: 'user' | 'ai';
    content: string;
    type?: string;
    citations?: Array<{ book: string; page: number; excerpt: string; relevance: number }>;
}

interface ChatSession {
    id: number;
    title: string;
    mode: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message_preview?: string;
}

const looksLikeProviderErrorResponse = (text: string) => {
    const normalized = text.toLowerCase();
    return (
        normalized.includes('no auto mode endpoints provided') ||
        normalized.includes('no endpoints provided') ||
        normalized.includes('model endpoint not found') ||
        normalized.includes('service unavailable') ||
        normalized.includes('upstream request failed')
    );
};

export default function AITutorPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState<'tutor' | 'mnemonic' | 'explain' | 'textbook' | 'analyze'>('tutor');
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
    const [showHistory, setShowHistory] = useState(false);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const chatRef = useRef<HTMLDivElement>(null);
    const lastAiMessageRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    // Load chat sessions on mount
    useEffect(() => {
        if (isAuthenticated) {
            loadSessions();
        }
    }, [isAuthenticated]);

    const loadSessions = async () => {
        setLoadingSessions(true);
        try {
            const res = await aiAPI.getChatSessions();
            setSessions(res.data || []);
        } catch {
            // Keep chat usable even if history endpoint is temporarily unavailable.
            setSessions([]);
        } finally {
            setLoadingSessions(false);
        }
    };

    const loadSession = async (sessionId: number) => {
        try {
            const res = await aiAPI.getChatSession(sessionId);
            setMessages(res.data.messages || []);
            setCurrentSessionId(sessionId);
            setMode(res.data.mode || 'tutor');
            setShowHistory(false);
            // Scroll to top when loading a session
            setTimeout(() => {
                if (chatRef.current) {
                    chatRef.current.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }, 100);
        } catch {
            setShowHistory(false);
        }
    };

    const startNewChat = () => {
        setMessages([]);
        setCurrentSessionId(null);
        setShowHistory(false);
    };

    const deleteSession = async (sessionId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await aiAPI.deleteChatSession(sessionId);
            setSessions(prev => prev.filter(s => s.id !== sessionId));
            if (currentSessionId === sessionId) {
                startNewChat();
            }
        } catch {
            // Ignore deletion failures silently to avoid breaking chat flow.
        }
    };

    // Scroll to show the AI answer from top when it's generated
    const scrollToLatestAiMessage = useCallback(() => {
        // Wait for render, then scroll to last AI message
        setTimeout(() => {
            if (lastAiMessageRef.current && chatRef.current) {
                const messageTop = lastAiMessageRef.current.offsetTop;
                chatRef.current.scrollTo({
                    top: Math.max(0, messageTop - 20), // 20px padding from top
                    behavior: 'smooth'
                });
            }
        }, 100);
    }, []);

    const handleSend = async () => {
        if (!input.trim() || loading) return;
        const userMsg = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMsg, type: mode }]);
        setLoading(true);

        try {
            let response: string;
            let citations: Message['citations'] = undefined;

            if (mode === 'tutor') {
                const res = await aiAPI.askTutor({ question: userMsg });
                response = res.data.response;
            } else if (mode === 'mnemonic') {
                const res = await aiAPI.generateMnemonic({ topic: userMsg });
                response = res.data.mnemonic;
            } else if (mode === 'explain') {
                const res = await aiAPI.explain({ concept: userMsg });
                response = res.data.explanation;
            } else if (mode === 'textbook') {
                const res = await aiAPI.ragAnswer({ question: userMsg });
                response = res.data.answer;
                citations = res.data.citations;
            } else {
                const res = await aiAPI.analyzeQuestion({ question_text: userMsg });
                response = res.data.analysis;
            }

            if (!response || looksLikeProviderErrorResponse(response)) {
                response = '⚠️ AI is temporarily unavailable right now. Please retry in a few seconds.';
            }

            setMessages(prev => [...prev, { role: 'ai', content: response, type: mode, citations }]);
            // Scroll to show AI answer from top after it's added
            scrollToLatestAiMessage();
            // Refresh sessions to include the new one
            loadSessions();
        } catch (err: unknown) {
            const statusCode = (err as { response?: { status?: number; data?: unknown } })?.response?.status;
            const errorPayload = (err as { response?: { data?: unknown } })?.response?.data;
            const is429 = statusCode === 429;
            const message = is429
                ? '⚠️ **AI Tokens Exhausted** — Your daily/weekly free tokens are used up. [Buy more tokens](/tokens) to continue using AI features.'
                : `⚠️ ${extractApiErrorMessage(errorPayload, 'Failed to get a response from AI. Please try again shortly.')}`;

            setMessages(prev => [...prev, {
                role: 'ai',
                content: message,
                type: mode
            }]);
            scrollToLatestAiMessage();
        } finally {
            setLoading(false);
        }
    };

    // Format date for display
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    // Get mode icon for history
    const getModeIcon = (m: string) => {
        switch (m) {
            case 'tutor': return Brain;
            case 'mnemonic': return Sparkles;
            case 'explain': return BookOpen;
            case 'textbook': return Search;
            case 'analyze': return FileText;
            default: return MessageSquare;
        }
    };

    const modes = [
        { key: 'tutor' as const, label: 'AI Tutor', icon: Brain, color: '#0e7490', desc: 'Ask any medical question' },
        { key: 'mnemonic' as const, label: 'Mnemonic', icon: Sparkles, color: '#d97706', desc: 'Generate memory tricks' },
        { key: 'explain' as const, label: 'Explain', icon: BookOpen, color: '#0284c7', desc: 'Concept from basics' },
        { key: 'textbook' as const, label: 'Textbook Search', icon: Search, color: '#0f766e', desc: 'Search standard textbooks via RAG' },
        { key: 'analyze' as const, label: 'Analyze Q', icon: FileText, color: '#0369a1', desc: 'Analyze a CMS question' },
    ];

    const suggestions: Record<string, string[]> = {
        tutor: [
            'What is the mechanism of edema in nephrotic syndrome?',
            'Explain the pathophysiology of myocardial infarction',
            'Differences between nephrotic and nephritic syndrome',
        ],
        mnemonic: [
            'Causes of pancreatitis',
            'Cranial nerves and their functions',
            'Features of nephrotic syndrome',
        ],
        explain: [
            'Renin-angiotensin-aldosterone system',
            'Mechanism of action of beta-blockers',
            'Apgar scoring system for neonates',
        ],
        textbook: [
            'What does Harrison say about treatment of pneumonia?',
            'Park PSM chapter on immunization schedule',
            'Ghai Pediatrics on neonatal jaundice management',
        ],
        analyze: [
            'Paste a CMS MCQ here to get full concept analysis',
            'Which drug is used in malignant hyperthermia?',
        ],
    };

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content flex flex-col" style={{ height: 'calc(100vh - 0px)' }}>
                <Header />
                {/* Header with History Toggle */}
                <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Brain className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                            AI Tutor
                        </h1>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Doctor-ready assistant with textbook search, concept coaching, and exam-mode reasoning</p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={startNewChat}
                            className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all hover:-translate-y-0.5"
                            style={{
                                background: 'rgba(14, 116, 144, 0.08)',
                                borderColor: 'rgba(14, 116, 144, 0.28)',
                                color: '#0e7490',
                            }}>
                            <Plus className="w-4 h-4" />
                            New Chat
                        </button>
                        <button
                            onClick={() => setShowHistory(!showHistory)}
                            className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all hover:-translate-y-0.5 ${showHistory ? 'scale-[1.02]' : ''}`}
                            style={{
                                background: showHistory ? 'rgba(2, 132, 199, 0.15)' : 'rgba(139, 149, 168, 0.05)',
                                borderColor: showHistory ? '#0284c7' : 'transparent',
                                color: showHistory ? '#0284c7' : 'var(--text-secondary)',
                            }}>
                            <History className="w-4 h-4" />
                            History {sessions.length > 0 && `(${sessions.length})`}
                        </button>
                    </div>
                </div>

                {/* Chat History Panel */}
                {showHistory && (
                    <div className="mb-4 glass-card p-4 animate-fadeInUp" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-semibold flex items-center gap-2">
                                <History className="w-4 h-4" style={{ color: '#0284c7' }} />
                                Chat History
                            </h3>
                            <button onClick={() => setShowHistory(false)} className="p-1 hover:bg-white/10 rounded">
                                <X className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                            </button>
                        </div>
                        {loadingSessions ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                            </div>
                        ) : sessions.length === 0 ? (
                            <div className="text-center py-8">
                                <MessageSquare className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--text-secondary)', opacity: 0.5 }} />
                                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No chat history yet</p>
                                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>Start a conversation to save it here</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {sessions.map(session => {
                                    const ModeIcon = getModeIcon(session.mode);
                                    const isActive = currentSessionId === session.id;
                                    return (
                                        <div
                                            key={session.id}
                                            onClick={() => loadSession(session.id)}
                                            className={`group flex cursor-pointer items-center gap-3 rounded-xl p-3 transition-all ${isActive ? 'scale-[1.01]' : 'hover:scale-[1.005]'}`}
                                            style={{
                                                background: isActive ? 'rgba(14, 116, 144, 0.12)' : 'rgba(139, 149, 168, 0.05)',
                                                border: `1px solid ${isActive ? 'rgba(14, 116, 144, 0.28)' : 'transparent'}`,
                                            }}>
                                            <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                                                style={{ background: isActive ? 'var(--gradient-primary)' : 'rgba(139, 149, 168, 0.1)' }}>
                                                <ModeIcon className="w-4 h-4" style={{ color: isActive ? 'white' : 'var(--text-secondary)' }} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate" style={{ color: isActive ? '#0e7490' : 'var(--text-primary)' }}>
                                                    {session.title || 'Untitled Chat'}
                                                </p>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                        <Clock className="w-3 h-3 inline mr-1" />
                                                        {formatDate(session.updated_at)}
                                                    </span>
                                                    <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(139, 149, 168, 0.1)', color: 'var(--text-secondary)' }}>
                                                        {session.message_count} msgs
                                                    </span>
                                                </div>
                                            </div>
                                            <button
                                                onClick={(e) => deleteSession(session.id, e)}
                                                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all hover:bg-red-500/20"
                                                style={{ color: '#ef4444' }}>
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}

                {/* Mode Selector */}
                <div className="flex flex-wrap gap-2 mb-4">
                    {modes.map(m => (
                        <button key={m.key} onClick={() => setMode(m.key)}
                            className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all ${mode === m.key ? 'scale-[1.02]' : ''}`}
                            style={{
                                background: mode === m.key ? `${m.color}20` : 'rgba(139, 149, 168, 0.05)',
                                borderColor: mode === m.key ? m.color : 'transparent',
                                color: mode === m.key ? m.color : 'var(--text-secondary)',
                            }}>
                            <m.icon className="w-4 h-4" />
                            {m.label}
                        </button>
                    ))}
                </div>

                {/* Chat Area */}
                <div className="relative flex-1">
                    <div ref={chatRef} className="h-full overflow-y-auto space-y-4 mb-4 pr-2" style={{ maxHeight: 'calc(100vh - 300px)' }}>
                    {messages.length === 0 ? (
                        <div className="text-center py-12">
                            <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center animate-float"
                                style={{ background: 'var(--gradient-primary)' }}>
                                <Lightbulb className="w-8 h-8 text-white" />
                            </div>
                            <h3 className="text-lg font-bold mb-2">
                                {modes.find(m => m.key === mode)?.desc}
                            </h3>
                            <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                                {mode === 'textbook' ? 'Searches across Harrison, Ghai, Nelson & Park textbooks' : 'Powered by Gemini + Groq AI'}
                            </p>
                            <div className="flex flex-wrap justify-center gap-2 max-w-2xl mx-auto">
                                {(suggestions[mode] || []).map((s, i) => (
                                    <button key={i} onClick={() => { setInput(s); }}
                                        className="text-xs px-4 py-2 rounded-xl transition-all hover:-translate-y-0.5"
                                        style={{ background: 'rgba(14, 116, 144, 0.08)', border: '1px solid rgba(14, 116, 144, 0.2)', color: 'var(--accent-primary)' }}>
                                        {s}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        messages.map((msg, i) => {
                            const isLastAiMessage = msg.role === 'ai' && i === messages.length - 1;
                            return (
                            <div
                                key={i}
                                ref={isLastAiMessage ? lastAiMessageRef : null}
                                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''} animate-fadeInUp`}
                            >
                                {msg.role === 'ai' && (
                                    <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                                        style={{ background: 'var(--gradient-primary)' }}>
                                        <Bot className="w-4 h-4 text-white" />
                                    </div>
                                )}
                                <div className="max-w-[80%]">
                                    <div className={`rounded-2xl p-4 text-sm leading-relaxed`}
                                        style={{
                                            background: msg.role === 'user' ? 'rgba(6, 182, 212, 0.15)' : 'var(--glass-bg)',
                                            border: `1px solid ${msg.role === 'user' ? 'rgba(6, 182, 212, 0.3)' : 'var(--glass-border)'}`,
                                        }}>
                                        {msg.role === 'ai' ? (
                                            <div className="ai-response text-foreground">
                                                {/*
                                                  NOTE: do NOT use Tailwind `prose` here.
                                                  Tailwind 4 doesn't ship the typography
                                                  plugin by default, so `prose prose-invert
                                                  prose-sm` adds zero styles — leaving raw
                                                  "#" markers visible. We hand-style every
                                                  element with `ai-response` CSS in
                                                  globals.css so headers/lists/quotes render
                                                  with proper hierarchy in light & dark.
                                                */}
                                                <ReactMarkdown
                                                    components={{
                                                        h1: ({ children }) => <h1 className="ai-h1">{children}</h1>,
                                                        h2: ({ children }) => <h2 className="ai-h2">{children}</h2>,
                                                        h3: ({ children }) => <h3 className="ai-h3">{children}</h3>,
                                                        h4: ({ children }) => <h4 className="ai-h4">{children}</h4>,
                                                        p: ({ children }) => {
                                                            const text = String(children);
                                                            if (text.includes('[PYQ') || text.includes('[High Yield]') || text.includes('Textbook Reference')) {
                                                                const parts = text.split(/(\[PYQ \d{4}\]|\[High Yield\]|\*\*Textbook Reference.*?\*\*)/g);
                                                                return (
                                                                    <p className="ai-p">
                                                                        {parts.map((part, index) => {
                                                                            if (part.startsWith('[PYQ')) {
                                                                                return <span key={index} className="ai-tag ai-tag-pink">📋 {part.replace('[', '').replace(']', '')}</span>;
                                                                            } else if (part === '[High Yield]') {
                                                                                return <span key={index} className="ai-tag ai-tag-amber">🔥 HIGH YIELD</span>;
                                                                            } else if (part.startsWith('**Textbook Reference')) {
                                                                                return <span key={index} className="ai-tag ai-tag-green">📚 {part.replace(/\*\*/g, '')}</span>;
                                                                            }
                                                                            return <span key={index}>{part}</span>;
                                                                        })}
                                                                    </p>
                                                                );
                                                            }
                                                            return <p className="ai-p">{children}</p>;
                                                        },
                                                        strong: ({ children }) => <strong className="ai-strong">{children}</strong>,
                                                        em: ({ children }) => <em className="ai-em">{children}</em>,
                                                        ul: ({ children }) => <ul className="ai-ul">{children}</ul>,
                                                        ol: ({ children }) => <ol className="ai-ol">{children}</ol>,
                                                        li: ({ children }) => (
                                                            <li className="ai-li">
                                                                <span className="ai-li-dot" />
                                                                <span>{children}</span>
                                                            </li>
                                                        ),
                                                        code: ({ children, className }) => {
                                                            if (className?.includes('language-')) {
                                                                return <pre className="ai-pre"><code>{children}</code></pre>;
                                                            }
                                                            return <code className="ai-code">{children}</code>;
                                                        },
                                                        blockquote: ({ children }) => (
                                                            <blockquote className="ai-blockquote">{children}</blockquote>
                                                        ),
                                                        hr: () => <hr className="ai-hr" />,
                                                        table: ({ children }) => (
                                                            <div className="ai-table-wrap">
                                                                <table className="ai-table">{children}</table>
                                                            </div>
                                                        ),
                                                        th: ({ children }) => <th className="ai-th">{children}</th>,
                                                        td: ({ children }) => <td className="ai-td">{children}</td>,
                                                        a: ({ href, children }) => <a href={href} className="ai-link" target="_blank" rel="noreferrer">{children}</a>,
                                                    }}
                                                >
                                                    {msg.content}
                                                </ReactMarkdown>
                                            </div>
                                        ) : (
                                            <p>{msg.content}</p>
                                        )}
                                    </div>
                                    {/* Textbook Citations */}
                                    {msg.citations && msg.citations.length > 0 && (
                                        <div className="mt-2 space-y-1">
                                            <div className="text-xs font-medium" style={{ color: '#10b981' }}>📚 Textbook References:</div>
                                            {msg.citations.map((c, j) => (
                                                <div key={j} className="text-xs p-2 rounded-lg"
                                                    style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.15)' }}>
                                                    <span className="font-medium" style={{ color: '#10b981' }}>{c.book}</span>
                                                    <span style={{ color: 'var(--text-secondary)' }}> — p.{c.page}</span>
                                                    <span className="ml-2 opacity-60">({Math.round(c.relevance * 100)}% match)</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                {msg.role === 'user' && (
                                    <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                                        style={{ background: 'rgba(139, 92, 246, 0.2)' }}>
                                        <User className="w-4 h-4" style={{ color: '#8b5cf6' }} />
                                    </div>
                                )}
                            </div>
                        );
                        })
                    )}
                    {loading && (
                        <div className="flex gap-3 animate-fadeInUp">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-primary)' }}>
                                <Bot className="w-4 h-4 text-white" />
                            </div>
                            <div className="glass-card p-4 flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                    {mode === 'textbook' ? '📚 Searching textbooks & references...' : '🧠 Researching your question across medical literature...'}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                    {/* Scroll to top button - shows when there are messages */}
                    {messages.length > 3 && (
                        <button
                            onClick={() => chatRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
                            className="absolute bottom-4 right-4 p-2 rounded-full shadow-lg transition-all hover:scale-110"
                            style={{
                                background: 'var(--gradient-primary)',
                                border: '1px solid var(--glass-border)',
                            }}
                            title="Scroll to top"
                        >
                            <ChevronDown className="w-5 h-5 text-white rotate-180" />
                        </button>
                    )}
                </div>

                {/* Input */}
                <div className="glass-card p-3 flex items-center gap-3 sticky bottom-0">
                    <input
                        className="input-field flex-1"
                        placeholder={
                            mode === 'tutor' ? 'Ask a medical question...' :
                                mode === 'mnemonic' ? 'Enter a topic for mnemonic...' :
                                    mode === 'explain' ? 'Enter a concept to explain...' :
                                        mode === 'textbook' ? 'Search textbooks (Harrison, Ghai, Park, Nelson)...' :
                                            'Paste a CMS question to analyze...'
                        }
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSend()}
                        disabled={loading}
                    />
                    <button onClick={handleSend} disabled={loading || !input.trim()} className="btn-primary py-3 px-4 rounded-xl">
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
