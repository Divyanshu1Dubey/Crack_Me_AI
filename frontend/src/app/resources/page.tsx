/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { resourcesAPI } from '@/lib/api';
import {
    FileText, Download, BookOpen, GraduationCap, HelpCircle,
    Clock, Target, DollarSign, Users, ChevronDown, ChevronUp,
    Shield, Award, Stethoscope, ScrollText, ExternalLink
} from 'lucide-react';

interface ResourceItem {
    id: string;
    name: string;
    filename: string;
    category: string;
}

interface ResourceCategory {
    title: string;
    items: ResourceItem[];
}

interface FAQ {
    q: string;
    a: string;
}

export default function ResourcesPage() {
    const [catalog, setCatalog] = useState<Record<string, ResourceCategory>>({});
    const [guide, setGuide] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'documents' | 'guide' | 'faq' | 'books'>('guide');
    const [openFaq, setOpenFaq] = useState<number | null>(null);

    useEffect(() => {
        Promise.all([
            resourcesAPI.getCatalog().catch(() => ({ data: {} })),
            resourcesAPI.getExamGuide().catch(() => ({ data: null })),
        ]).then(([catRes, guideRes]) => {
            setCatalog(catRes.data || {});
            setGuide(guideRes.data);
        }).finally(() => setLoading(false));
    }, []);

    const downloadResource = (id: string) => {
        window.open(resourcesAPI.downloadUrl(id), '_blank');
    };

    const categoryIcons: Record<string, any> = {
        official_documents: ScrollText,
        exam_resources: GraduationCap,
        certificates: Shield,
        experience_travel: FileText,
    };

    const categoryColors: Record<string, string> = {
        official_documents: '#06b6d4',
        exam_resources: '#8b5cf6',
        certificates: '#f59e0b',
        experience_travel: '#10b981',
    };

    const tabs = [
        { key: 'guide' as const, label: 'CMS Exam Guide', icon: GraduationCap },
        { key: 'documents' as const, label: 'Official Documents', icon: FileText },
        { key: 'faq' as const, label: 'FAQ', icon: HelpCircle },
        { key: 'books' as const, label: 'Recommended Books', icon: BookOpen },
    ];

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <BookOpen className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                        Resources & CMS Guide
                    </h1>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                        Complete one-stop resource for UPSC CMS — official forms, exam guide, FAQ, and study material
                    </p>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                    {tabs.map(t => (
                        <button key={t.key} onClick={() => setActiveTab(t.key)}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap"
                            style={{
                                background: activeTab === t.key ? 'var(--accent-primary)' : 'var(--glass-bg)',
                                color: activeTab === t.key ? '#fff' : 'var(--text-secondary)',
                                border: `1px solid ${activeTab === t.key ? 'var(--accent-primary)' : 'var(--glass-border)'}`,
                            }}>
                            <t.icon className="w-4 h-4" />
                            {t.label}
                        </button>
                    ))}
                </div>

                {loading ? (
                    <div className="glass-card p-8 text-center"><div className="animate-pulse gradient-text">Loading resources...</div></div>
                ) : (
                    <>
                        {/* ===== CMS EXAM GUIDE ===== */}
                        {activeTab === 'guide' && guide && (
                            <div className="space-y-6">
                                {/* Exam Overview */}
                                <div className="glass-card p-6">
                                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                                        <Stethoscope className="w-5 h-5" style={{ color: '#06b6d4' }} />
                                        {guide.exam_name}
                                    </h2>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        {[
                                            { icon: <Users className="w-5 h-5" />, label: 'Conducting Body', value: guide.conducting_body, color: '#06b6d4' },
                                            { icon: <Clock className="w-5 h-5" />, label: 'Frequency', value: guide.frequency, color: '#8b5cf6' },
                                            { icon: <Target className="w-5 h-5" />, label: 'Mode', value: guide.mode, color: '#f59e0b' },
                                            { icon: <Award className="w-5 h-5" />, label: 'Total Marks', value: `${guide.total_marks} marks`, color: '#10b981' },
                                        ].map((s, i) => (
                                            <div key={i} className="p-4 rounded-xl" style={{ background: `${s.color}08`, border: `1px solid ${s.color}20` }}>
                                                <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2" style={{ background: `${s.color}15`, color: s.color }}>{s.icon}</div>
                                                <div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>{s.label}</div>
                                                <div className="text-sm font-bold">{s.value}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Paper Pattern */}
                                <div className="grid md:grid-cols-2 gap-6">
                                    {['paper1', 'paper2'].map(key => {
                                        const paper = guide.paper_pattern[key];
                                        const color = key === 'paper1' ? '#06b6d4' : '#8b5cf6';
                                        return (
                                            <div key={key} className="glass-card p-6">
                                                <h3 className="font-bold mb-1 text-lg" style={{ color }}>{paper.title}</h3>
                                                <div className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                                                    {paper.total_questions} Questions · {paper.total_marks} Marks · {paper.duration_minutes} Minutes
                                                </div>
                                                <div className="space-y-3">
                                                    {paper.subjects.map((s: any, i: number) => (
                                                        <div key={i} className="flex justify-between items-center p-3 rounded-lg" style={{ background: `${color}08` }}>
                                                            <span className="text-sm font-medium">{s.name}</span>
                                                            <span className="badge" style={{ background: `${color}15`, color }}>{s.questions} Qs</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Marking Scheme */}
                                <div className="glass-card p-6">
                                    <h3 className="font-bold mb-4 flex items-center gap-2">
                                        <Target className="w-5 h-5" style={{ color: '#ef4444' }} />
                                        Marking Scheme
                                    </h3>
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                                            <div className="text-lg font-bold" style={{ color: '#10b981' }}>+2.08</div>
                                            <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Correct Answer</div>
                                        </div>
                                        <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                                            <div className="text-lg font-bold" style={{ color: '#ef4444' }}>−0.69</div>
                                            <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Wrong Answer (1/3 negative)</div>
                                        </div>
                                        <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(139, 149, 168, 0.08)', border: '1px solid rgba(139, 149, 168, 0.2)' }}>
                                            <div className="text-lg font-bold" style={{ color: 'var(--text-secondary)' }}>0</div>
                                            <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Unanswered</div>
                                        </div>
                                    </div>
                                </div>

                                {/* Eligibility */}
                                <div className="glass-card p-6">
                                    <h3 className="font-bold mb-4 flex items-center gap-2">
                                        <Shield className="w-5 h-5" style={{ color: '#f59e0b' }} />
                                        Eligibility Criteria
                                    </h3>
                                    <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(6, 182, 212, 0.06)', border: '1px solid rgba(6, 182, 212, 0.15)' }}>
                                        <strong style={{ color: 'var(--accent-primary)' }}>Qualification:</strong>{' '}
                                        <span style={{ color: 'var(--text-secondary)' }}>{guide.eligibility.qualification}</span>
                                    </div>
                                    <div className="grid md:grid-cols-2 gap-4">
                                        <div>
                                            <h4 className="text-sm font-bold mb-2">Age Limits</h4>
                                            <div className="space-y-2">
                                                {Object.entries(guide.eligibility.age_limit).map(([cat, age]) => (
                                                    <div key={cat} className="flex justify-between text-sm p-2 rounded" style={{ background: 'rgba(139, 149, 168, 0.05)' }}>
                                                        <span className="uppercase text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{cat.replace('_', '/')}</span>
                                                        <span>{age as string}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-bold mb-2">Attempt Limits</h4>
                                            <div className="space-y-2">
                                                {Object.entries(guide.eligibility.attempts).map(([cat, attempts]) => (
                                                    <div key={cat} className="flex justify-between text-sm p-2 rounded" style={{ background: 'rgba(139, 149, 168, 0.05)' }}>
                                                        <span className="uppercase text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{cat.replace('_', '/')}</span>
                                                        <span>{attempts as string}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Salary & Posts */}
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="glass-card p-6">
                                        <h3 className="font-bold mb-4 flex items-center gap-2">
                                            <DollarSign className="w-5 h-5" style={{ color: '#10b981' }} />
                                            Salary & Benefits
                                        </h3>
                                        <div className="space-y-3 text-sm">
                                            <div className="p-3 rounded-lg" style={{ background: 'rgba(16, 185, 129, 0.06)' }}>
                                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Pay Level</div>
                                                <div className="font-bold">{guide.salary.pay_level}</div>
                                            </div>
                                            <div className="p-3 rounded-lg" style={{ background: 'rgba(16, 185, 129, 0.06)' }}>
                                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Gross Monthly</div>
                                                <div className="font-bold">{guide.salary.gross_monthly}</div>
                                            </div>
                                            <div className="p-3 rounded-lg" style={{ background: 'rgba(16, 185, 129, 0.06)' }}>
                                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Perks</div>
                                                <div>{guide.salary.perks}</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="glass-card p-6">
                                        <h3 className="font-bold mb-4 flex items-center gap-2">
                                            <Users className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                                            Recruiting For
                                        </h3>
                                        <div className="space-y-2">
                                            {guide.recruiting_for.map((post: string, i: number) => (
                                                <div key={i} className="flex items-start gap-2 text-sm p-2 rounded" style={{ background: 'rgba(139, 92, 246, 0.06)' }}>
                                                    <Award className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#8b5cf6' }} />
                                                    <span>{post}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ===== OFFICIAL DOCUMENTS ===== */}
                        {activeTab === 'documents' && (
                            <div className="space-y-6">
                                {Object.entries(catalog).map(([key, category]) => {
                                    const Icon = categoryIcons[key] || FileText;
                                    const color = categoryColors[key] || '#06b6d4';
                                    return (
                                        <div key={key} className="glass-card p-6">
                                            <h3 className="font-bold mb-4 flex items-center gap-2">
                                                <Icon className="w-5 h-5" style={{ color }} />
                                                {category.title}
                                            </h3>
                                            <div className="grid md:grid-cols-2 gap-3">
                                                {category.items.map(item => (
                                                    <button key={item.id} onClick={() => downloadResource(item.id)}
                                                        className="flex items-center gap-3 p-4 rounded-xl text-left group transition-all hover:scale-[1.02]"
                                                        style={{ background: `${color}06`, border: `1px solid ${color}15` }}>
                                                        <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                                            style={{ background: `${color}15`, color }}>
                                                            <Download className="w-5 h-5" />
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <div className="text-sm font-medium truncate">{item.name}</div>
                                                            <div className="text-xs flex items-center gap-1 mt-1" style={{ color: 'var(--text-secondary)' }}>
                                                                <FileText className="w-3 h-3" /> PDF · Click to download
                                                            </div>
                                                        </div>
                                                        <ExternalLink className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color }} />
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        {/* ===== FAQ ===== */}
                        {activeTab === 'faq' && guide?.faq && (
                            <div className="space-y-3">
                                <div className="glass-card p-6 mb-4">
                                    <h2 className="font-bold flex items-center gap-2 mb-2">
                                        <HelpCircle className="w-5 h-5" style={{ color: '#f59e0b' }} />
                                        Frequently Asked Questions
                                    </h2>
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        Common doubts answered with verified information from official UPSC sources
                                    </p>
                                </div>
                                {guide.faq.map((faq: FAQ, i: number) => (
                                    <div key={i} className="glass-card overflow-hidden">
                                        <button onClick={() => setOpenFaq(openFaq === i ? null : i)}
                                            className="w-full flex items-start gap-3 p-5 text-left">
                                            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-sm font-bold"
                                                style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-primary)' }}>
                                                Q{i + 1}
                                            </div>
                                            <div className="flex-1">
                                                <div className="text-sm font-medium">{faq.q}</div>
                                            </div>
                                            {openFaq === i ? <ChevronUp className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--accent-primary)' }} /> :
                                                <ChevronDown className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--text-secondary)' }} />}
                                        </button>
                                        {openFaq === i && (
                                            <div className="px-5 pb-5 ml-11">
                                                <div className="p-4 rounded-lg text-sm leading-relaxed"
                                                    style={{ background: 'rgba(6, 182, 212, 0.04)', border: '1px solid rgba(6, 182, 212, 0.1)', color: 'var(--text-secondary)' }}>
                                                    {faq.a}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* ===== RECOMMENDED BOOKS ===== */}
                        {activeTab === 'books' && guide?.standard_textbooks && (
                            <div className="space-y-4">
                                <div className="glass-card p-6 mb-2">
                                    <h2 className="font-bold flex items-center gap-2 mb-2">
                                        <BookOpen className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                                        Standard Textbooks for UPSC CMS
                                    </h2>
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        These are the gold-standard references used in UPSC CMS preparation. Answers are derived from these books.
                                    </p>
                                </div>
                                {guide.standard_textbooks.map((entry: any, i: number) => {
                                    const colors = ['#06b6d4', '#f59e0b', '#3b82f6', '#ec4899', '#10b981'];
                                    const c = colors[i % colors.length];
                                    return (
                                        <div key={i} className="glass-card p-5">
                                            <div className="flex items-center gap-3 mb-3">
                                                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${c}15`, color: c }}>
                                                    <Stethoscope className="w-5 h-5" />
                                                </div>
                                                <h3 className="font-bold" style={{ color: c }}>{entry.subject}</h3>
                                            </div>
                                            <div className="space-y-2 ml-13">
                                                {entry.books.map((book: string, j: number) => (
                                                    <div key={j} className="flex items-center gap-2 text-sm p-2 rounded-lg" style={{ background: `${c}06` }}>
                                                        <BookOpen className="w-4 h-4 flex-shrink-0" style={{ color: c }} />
                                                        <span>{book}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
