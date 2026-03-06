/**
 * ai-tutor/page.tsx — AI Medical Tutor chat interface.
 * Real-time chat with Gemini/Groq AI for CMS exam preparation.
 * Features: suggested starter prompts, markdown-rendered responses,
 * chat history, auto-scroll, token consumption with 429 handling.
 */
'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { aiAPI } from '@/lib/api';
import { Brain, Send, Sparkles, BookOpen, Lightbulb, Bot, User, Loader2, Search, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Message {
    role: 'user' | 'ai';
    content: string;
    type?: string;
    citations?: Array<{ book: string; page: number; excerpt: string; relevance: number }>;
}

export default function AITutorPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState<'tutor' | 'mnemonic' | 'explain' | 'textbook' | 'analyze'>('tutor');
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (chatRef.current) {
            chatRef.current.scrollTop = chatRef.current.scrollHeight;
        }
    }, [messages]);

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
            setMessages(prev => [...prev, { role: 'ai', content: response, type: mode, citations }]);
        } catch (err: any) {
            const is429 = err?.response?.status === 429;
            setMessages(prev => [...prev, {
                role: 'ai',
                content: is429
                    ? '⚠️ **AI Tokens Exhausted** — Your daily/weekly free tokens are used up. [Buy more tokens](/tokens) to continue using AI features.'
                    : '⚠️ Failed to get a response. Please check your API keys in backend/.env and try again.',
                type: mode
            }]);
        } finally {
            setLoading(false);
        }
    };

    const modes = [
        { key: 'tutor' as const, label: 'AI Tutor', icon: Brain, color: '#06b6d4', desc: 'Ask any medical question' },
        { key: 'mnemonic' as const, label: 'Mnemonic', icon: Sparkles, color: '#f59e0b', desc: 'Generate memory tricks' },
        { key: 'explain' as const, label: 'Explain', icon: BookOpen, color: '#8b5cf6', desc: 'Concept from basics' },
        { key: 'textbook' as const, label: 'Textbook Search', icon: Search, color: '#10b981', desc: 'Search standard textbooks via RAG' },
        { key: 'analyze' as const, label: 'Analyze Q', icon: FileText, color: '#ec4899', desc: 'Analyze a CMS question' },
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
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content flex flex-col" style={{ height: 'calc(100vh - 0px)' }}>
                {/* Header */}
                <div className="mb-4">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Brain className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                        AI Tutor
                    </h1>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Your personal CMS preparation assistant — now with textbook RAG search</p>
                </div>

                {/* Mode Selector */}
                <div className="flex flex-wrap gap-2 mb-4">
                    {modes.map(m => (
                        <button key={m.key} onClick={() => setMode(m.key)}
                            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all ${mode === m.key ? 'scale-105' : ''}`}
                            style={{
                                background: mode === m.key ? `${m.color}20` : 'rgba(139, 149, 168, 0.05)',
                                border: `1px solid ${mode === m.key ? m.color : 'transparent'}`,
                                color: mode === m.key ? m.color : 'var(--text-secondary)',
                            }}>
                            <m.icon className="w-4 h-4" />
                            {m.label}
                        </button>
                    ))}
                </div>

                {/* Chat Area */}
                <div ref={chatRef} className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2" style={{ maxHeight: 'calc(100vh - 300px)' }}>
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
                                        className="text-xs px-4 py-2 rounded-xl transition-all hover:scale-105"
                                        style={{ background: 'rgba(6, 182, 212, 0.08)', border: '1px solid rgba(6, 182, 212, 0.2)', color: 'var(--accent-primary)' }}>
                                        {s}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        messages.map((msg, i) => (
                            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''} animate-fadeInUp`}>
                                {msg.role === 'ai' && (
                                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
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
                                            <div className="prose prose-invert prose-sm max-w-none ai-response">
                                                <ReactMarkdown
                                                    components={{
                                                        h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2 pb-2" style={{ color: 'var(--accent-primary)', borderBottom: '1px solid var(--glass-border)' }}>{children}</h1>,
                                                        h2: ({ children }) => <h2 className="text-lg font-bold mt-4 mb-2 pb-1" style={{ color: 'var(--accent-primary)', borderBottom: '1px solid rgba(6,182,212,0.2)' }}>{children}</h2>,
                                                        h3: ({ children }) => <h3 className="text-base font-bold mt-3 mb-1" style={{ color: '#f59e0b' }}>{children}</h3>,
                                                        h4: ({ children }) => <h4 className="text-sm font-bold mt-2 mb-1" style={{ color: '#8b5cf6' }}>{children}</h4>,
                                                        p: ({ children }) => {
                                                            const text = String(children);
                                                            if (text.includes('[PYQ') || text.includes('[High Yield]') || text.includes('Textbook Reference')) {
                                                                const parts = text.split(/(\[PYQ \d{4}\]|\[High Yield\]|\*\*Textbook Reference.*?\*\*)/g);
                                                                return (
                                                                    <p className="mb-2 leading-relaxed">
                                                                        {parts.map((part, index) => {
                                                                            if (part.startsWith('[PYQ')) {
                                                                                return <span key={index} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold mr-1 mb-1" style={{ background: 'rgba(236, 72, 153, 0.15)', color: '#ec4899', border: '1px solid rgba(236, 72, 153, 0.3)' }}>📋 {part.replace('[', '').replace(']', '')}</span>;
                                                                            } else if (part === '[High Yield]') {
                                                                                return <span key={index} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold mr-1 mb-1" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.3)' }}>🔥 HIGH YIELD</span>;
                                                                            } else if (part.startsWith('**Textbook Reference')) {
                                                                                return <span key={index} className="block mt-2 px-3 py-2 rounded-lg text-xs font-medium" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)' }}>📚 {part.replace(/\*\*/g, '')}</span>;
                                                                            }
                                                                            return <span key={index}>{part}</span>;
                                                                        })}
                                                                    </p>
                                                                );
                                                            }
                                                            return <p className="mb-2 leading-relaxed">{children}</p>;
                                                        },
                                                        strong: ({ children }) => <strong className="font-bold" style={{ color: '#06b6d4' }}>{children}</strong>,
                                                        ul: ({ children }) => <ul className="my-2 space-y-1.5 ml-1">{children}</ul>,
                                                        ol: ({ children }) => <ol className="my-2 space-y-1.5 ml-1 list-decimal list-inside">{children}</ol>,
                                                        li: ({ children }) => (
                                                            <li className="flex items-start gap-2 text-sm leading-relaxed">
                                                                <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--accent-primary)' }} />
                                                                <span>{children}</span>
                                                            </li>
                                                        ),
                                                        code: ({ children, className }) => {
                                                            if (className?.includes('language-')) {
                                                                return <pre className="p-3 rounded-lg my-2 overflow-x-auto text-xs" style={{ background: 'var(--bg-primary)', border: '1px solid var(--glass-border)' }}><code>{children}</code></pre>;
                                                            }
                                                            return <code className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: 'rgba(6,182,212,0.1)', color: '#06b6d4' }}>{children}</code>;
                                                        },
                                                        blockquote: ({ children }) => (
                                                            <blockquote className="my-2 pl-3 py-1" style={{ borderLeft: '3px solid #f59e0b', background: 'rgba(245,158,11,0.05)', borderRadius: '0 8px 8px 0' }}>
                                                                {children}
                                                            </blockquote>
                                                        ),
                                                        hr: () => <hr className="my-3" style={{ borderColor: 'var(--glass-border)' }} />,
                                                        table: ({ children }) => (
                                                            <div className="overflow-x-auto my-2">
                                                                <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>{children}</table>
                                                            </div>
                                                        ),
                                                        th: ({ children }) => <th className="text-left px-3 py-2 text-xs font-bold" style={{ background: 'var(--bg-primary)', borderBottom: '2px solid var(--accent-primary)', color: 'var(--accent-primary)' }}>{children}</th>,
                                                        td: ({ children }) => <td className="px-3 py-2 text-xs" style={{ borderBottom: '1px solid var(--glass-border)' }}>{children}</td>,
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
                                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                                        style={{ background: 'rgba(139, 92, 246, 0.2)' }}>
                                        <User className="w-4 h-4" style={{ color: '#8b5cf6' }} />
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                    {loading && (
                        <div className="flex gap-3 animate-fadeInUp">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-primary)' }}>
                                <Bot className="w-4 h-4 text-white" />
                            </div>
                            <div className="glass-card p-4 flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                    {mode === 'textbook' ? 'Searching textbooks...' : 'Thinking...'}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Input */}
                <div className="glass-card p-3 flex items-center gap-3">
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
                    <button onClick={handleSend} disabled={loading || !input.trim()} className="btn-primary py-3 px-4">
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
