/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI, authAPI, questionsAPI } from '@/lib/api';
import {
    Users, BookOpen, FileText, AlertTriangle, TrendingUp,
    CheckCircle, XCircle, Clock, Shield, Megaphone, Plus, Trash2,
    Zap, MessageSquare, Gift
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';

interface DashboardData {
    total_users: number;
    active_today: number;
    total_questions: number;
    questions_with_answer: number;
    questions_with_explanation: number;
    answer_percentage: number;
    total_tests_taken: number;
    unresolved_feedback: number;
    recent_signups: { id: number; username: string; date_joined: string }[];
}

interface Announcement {
    id: number;
    title: string;
    message: string;
    priority: string;
    is_active: boolean;
    is_expired: boolean;
    created_at: string;
    expires_at: string | null;
}

const priorityColors: Record<string, string> = {
    low: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    normal: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    high: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    urgent: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

export default function AdminDashboardPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [data, setData] = useState<DashboardData | null>(null);
    const [announcements, setAnnouncements] = useState<Announcement[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ title: '', message: '', priority: 'normal', expires_at: '' });
    const [submitting, setSubmitting] = useState(false);
    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'feedback'>('overview');
    // Users & token management
    const [userList, setUserList] = useState<any[]>([]);
    const [usersLoading, setUsersLoading] = useState(false);
    const [grantUserId, setGrantUserId] = useState('');
    const [grantAmount, setGrantAmount] = useState('');
    const [grantNote, setGrantNote] = useState('');
    const [granting, setGranting] = useState(false);
    const [grantMsg, setGrantMsg] = useState('');
    // Feedback queue
    const [feedbackList, setFeedbackList] = useState<any[]>([]);
    const [feedbackLoading, setFeedbackLoading] = useState(false);

    useEffect(() => {
        if (!authLoading && (!isAuthenticated || user?.role !== 'admin')) {
            router.push('/dashboard');
            return;
        }
        if (isAuthenticated && user?.role === 'admin') {
            Promise.all([
                analyticsAPI.getAdminDashboard().catch(() => ({ data: null })),
                analyticsAPI.getAnnouncements().catch(() => ({ data: [] })),
            ]).then(([dashRes, annRes]) => {
                setData(dashRes.data);
                setAnnouncements(Array.isArray(annRes.data) ? annRes.data : annRes.data?.results || []);
                setLoading(false);
            });
        }
    }, [isAuthenticated, authLoading, user, router]);

    const handleCreateAnnouncement = async () => {
        if (!form.title.trim() || !form.message.trim()) return;
        setSubmitting(true);
        try {
            const payload: any = { title: form.title, message: form.message, priority: form.priority };
            if (form.expires_at) payload.expires_at = form.expires_at;
            const res = await analyticsAPI.createAnnouncement(payload);
            setAnnouncements([res.data, ...announcements]);
            setForm({ title: '', message: '', priority: 'normal', expires_at: '' });
            setShowForm(false);
        } catch { /* ignore */ }
        setSubmitting(false);
    };

    const handleDeleteAnnouncement = async (id: number) => {
        try {
            await analyticsAPI.deleteAnnouncement(id);
            setAnnouncements(announcements.filter(a => a.id !== id));
        } catch { /* ignore */ }
    };

    const fetchUsers = () => {
        setUsersLoading(true);
        authAPI.adminGetAllUsers()
            .then(res => setUserList(Array.isArray(res.data) ? res.data : res.data?.results || res.data?.users || []))
            .catch(() => {})
            .finally(() => setUsersLoading(false));
    };

    const fetchFeedback = () => {
        setFeedbackLoading(true);
        questionsAPI.getFeedback()
            .then(res => setFeedbackList(Array.isArray(res.data) ? res.data : res.data?.results || []))
            .catch(() => {})
            .finally(() => setFeedbackLoading(false));
    };

    const handleTabChange = (tab: 'overview' | 'users' | 'feedback') => {
        setActiveTab(tab);
        if (tab === 'users' && userList.length === 0) fetchUsers();
        if (tab === 'feedback' && feedbackList.length === 0) fetchFeedback();
    };

    const handleGrantTokens = async () => {
        if (!grantUserId || !grantAmount) return;
        setGranting(true);
        setGrantMsg('');
        try {
            const res = await authAPI.adminGrantTokens({
                user_id: Number(grantUserId),
                amount: Number(grantAmount),
                note: grantNote || undefined,
            });
            setGrantMsg(res.data?.message || 'Tokens granted!');
            setGrantAmount('');
            setGrantNote('');
            fetchUsers();
        } catch (err: any) {
            setGrantMsg(err?.response?.data?.error || 'Failed to grant tokens');
        }
        setGranting(false);
    };

    const handleResolveFeedback = async (id: number) => {
        try {
            await questionsAPI.resolveFeedback(id);
            setFeedbackList(feedbackList.map(f => f.id === id ? { ...f, is_resolved: true } : f));
        } catch { /* ignore */ }
    };

    if (authLoading || loading) {
        return (
            <div className="min-h-screen bg-background flex">
                <Sidebar />
                <div className="flex-1 flex flex-col">
                    <Header />
                    <main className="flex-1 p-6 flex items-center justify-center">
                        <div className="animate-pulse text-muted-foreground">Loading admin dashboard...</div>
                    </main>
                </div>
            </div>
        );
    }

    const stats = [
        { label: 'Total Users', value: data?.total_users || 0, icon: Users, color: 'text-blue-500' },
        { label: 'Active Today', value: data?.active_today || 0, icon: TrendingUp, color: 'text-green-500' },
        { label: 'Total Questions', value: data?.total_questions || 0, icon: BookOpen, color: 'text-purple-500' },
        { label: 'Tests Taken', value: data?.total_tests_taken || 0, icon: FileText, color: 'text-cyan-500' },
        { label: 'With Answers', value: `${data?.answer_percentage?.toFixed(1) || 0}%`, icon: CheckCircle, color: 'text-emerald-500' },
        { label: 'With Explanations', value: data?.questions_with_explanation || 0, icon: CheckCircle, color: 'text-teal-500' },
        { label: 'Unresolved Feedback', value: data?.unresolved_feedback || 0, icon: AlertTriangle, color: data?.unresolved_feedback ? 'text-amber-500' : 'text-slate-400' },
    ];

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 page-container space-y-6">
                    {/* Title */}
                    <div className="flex items-center gap-3">
                        <Shield className="w-7 h-7 text-primary" />
                        <div>
                            <h1 className="text-2xl font-bold">Admin Dashboard</h1>
                            <p className="text-sm text-muted-foreground">Platform overview & management</p>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
                        {[
                            { key: 'overview', label: 'Overview', icon: TrendingUp },
                            { key: 'users', label: 'Users & Tokens', icon: Users },
                            { key: 'feedback', label: 'Feedback Queue', icon: MessageSquare },
                        ].map(tab => (
                            <button key={tab.key}
                                onClick={() => handleTabChange(tab.key as 'overview' | 'users' | 'feedback')}
                                className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                                <tab.icon className="w-4 h-4" /> {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* ===== OVERVIEW TAB ===== */}
                    {activeTab === 'overview' && (<>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                        {stats.map(s => (
                            <Card key={s.label}>
                                <CardContent className="p-4 flex items-center gap-3">
                                    <s.icon className={`w-8 h-8 ${s.color} shrink-0`} />
                                    <div>
                                        <p className="text-2xl font-bold">{s.value}</p>
                                        <p className="text-xs text-muted-foreground">{s.label}</p>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Question Quality */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-lg">
                                <BookOpen className="w-5 h-5" /> Question Quality
                            </CardTitle>
                            <CardDescription>Answer and explanation coverage</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span>Questions with correct answers</span>
                                        <span className="font-medium">{data?.questions_with_answer}/{data?.total_questions}</span>
                                    </div>
                                    <div className="w-full bg-muted rounded-full h-2.5">
                                        <div
                                            className="bg-emerald-500 h-2.5 rounded-full transition-all"
                                            style={{ width: `${data?.answer_percentage || 0}%` }}
                                        />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span>Questions with explanations</span>
                                        <span className="font-medium">{data?.questions_with_explanation}/{data?.total_questions}</span>
                                    </div>
                                    <div className="w-full bg-muted rounded-full h-2.5">
                                        <div
                                            className="bg-teal-500 h-2.5 rounded-full transition-all"
                                            style={{ width: `${data?.total_questions ? (data.questions_with_explanation / data.total_questions * 100) : 0}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="grid lg:grid-cols-2 gap-6">
                        {/* Announcements */}
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Megaphone className="w-5 h-5" /> Announcements
                                    </CardTitle>
                                    <Button size="sm" variant={showForm ? 'outline' : 'default'} onClick={() => setShowForm(!showForm)}>
                                        <Plus className="w-4 h-4 mr-1" /> {showForm ? 'Cancel' : 'New'}
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {showForm && (
                                    <div className="space-y-2 p-3 rounded-lg border bg-muted/50">
                                        <Input placeholder="Title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
                                        <textarea
                                            className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                                            placeholder="Message..."
                                            value={form.message}
                                            onChange={e => setForm({ ...form, message: e.target.value })}
                                        />
                                        <div className="flex gap-2">
                                            <select
                                                className="rounded-md border bg-background px-3 py-2 text-sm"
                                                value={form.priority}
                                                onChange={e => setForm({ ...form, priority: e.target.value })}
                                            >
                                                <option value="low">Low</option>
                                                <option value="normal">Normal</option>
                                                <option value="high">High</option>
                                                <option value="urgent">Urgent</option>
                                            </select>
                                            <Input type="datetime-local" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} placeholder="Expires (optional)" />
                                            <Button size="sm" onClick={handleCreateAnnouncement} disabled={submitting}>
                                                {submitting ? 'Posting...' : 'Post'}
                                            </Button>
                                        </div>
                                    </div>
                                )}
                                {announcements.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No announcements yet</p>}
                                {announcements.map(a => (
                                    <div key={a.id} className="flex items-start gap-3 p-3 rounded-lg border">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-medium text-sm truncate">{a.title}</span>
                                                <Badge className={`text-[10px] px-1.5 ${priorityColors[a.priority] || ''}`}>{a.priority}</Badge>
                                                {a.is_expired && <Badge variant="outline" className="text-[10px]">Expired</Badge>}
                                            </div>
                                            <p className="text-xs text-muted-foreground line-clamp-2">{a.message}</p>
                                        </div>
                                        <Button variant="ghost" size="icon" className="shrink-0 h-8 w-8 text-destructive" onClick={() => handleDeleteAnnouncement(a.id)}>
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Recent Signups */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-lg">
                                    <Users className="w-5 h-5" /> Recent Signups
                                </CardTitle>
                                <CardDescription>Last 10 registered users</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {(!data?.recent_signups || data.recent_signups.length === 0) ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No recent signups</p>
                                ) : (
                                    <div className="space-y-2">
                                        {data.recent_signups.map(u => (
                                            <div key={u.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                                                        {u.username.charAt(0).toUpperCase()}
                                                    </div>
                                                    <span className="text-sm font-medium">{u.username}</span>
                                                </div>
                                                <span className="text-xs text-muted-foreground">
                                                    <Clock className="w-3 h-3 inline mr-1" />
                                                    {new Date(u.date_joined).toLocaleDateString()}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    </>)}

                    {/* ===== USERS & TOKENS TAB ===== */}
                    {activeTab === 'users' && (
                        <div className="space-y-6">
                            {/* Grant Tokens */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Gift className="w-5 h-5" /> Grant Tokens
                                    </CardTitle>
                                    <CardDescription>Give tokens to any user</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-wrap gap-3 items-end">
                                        <div>
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">User ID</label>
                                            <Input className="w-24" type="number" placeholder="ID"
                                                value={grantUserId} onChange={e => setGrantUserId(e.target.value)} />
                                        </div>
                                        <div>
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">Tokens</label>
                                            <Input className="w-24" type="number" placeholder="Amount"
                                                value={grantAmount} onChange={e => setGrantAmount(e.target.value)} />
                                        </div>
                                        <div className="flex-1 min-w-[200px]">
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">Note (optional)</label>
                                            <Input placeholder="Reason for granting tokens"
                                                value={grantNote} onChange={e => setGrantNote(e.target.value)} />
                                        </div>
                                        <Button onClick={handleGrantTokens} disabled={granting || !grantUserId || !grantAmount}>
                                            <Zap className="w-4 h-4 mr-1" /> {granting ? 'Granting...' : 'Grant'}
                                        </Button>
                                    </div>
                                    {grantMsg && <p className="text-sm mt-2 text-primary font-medium">{grantMsg}</p>}
                                </CardContent>
                            </Card>

                            {/* User List */}
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="flex items-center gap-2 text-lg">
                                            <Users className="w-5 h-5" /> All Users
                                        </CardTitle>
                                        <Button variant="outline" size="sm" onClick={fetchUsers} disabled={usersLoading}>
                                            {usersLoading ? 'Loading...' : 'Refresh'}
                                        </Button>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    {usersLoading ? (
                                        <p className="text-sm text-muted-foreground animate-pulse text-center py-4">Loading users...</p>
                                    ) : userList.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-4">No users found</p>
                                    ) : (
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead>
                                                    <tr className="border-b text-left text-muted-foreground">
                                                        <th className="pb-2 pr-4">ID</th>
                                                        <th className="pb-2 pr-4">Username</th>
                                                        <th className="pb-2 pr-4">Email</th>
                                                        <th className="pb-2 pr-4">Role</th>
                                                        <th className="pb-2 pr-4 text-right">Tokens</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {userList.map((u: any) => (
                                                        <tr key={u.id || u.user_id} className="border-b last:border-0 hover:bg-muted/50">
                                                            <td className="py-2 pr-4 text-muted-foreground">{u.id || u.user_id}</td>
                                                            <td className="py-2 pr-4 font-medium">{u.username}</td>
                                                            <td className="py-2 pr-4 text-muted-foreground">{u.email || '—'}</td>
                                                            <td className="py-2 pr-4">
                                                                <Badge variant={u.role === 'admin' ? 'default' : 'secondary'} className="text-[10px]">
                                                                    {u.role || 'student'}
                                                                </Badge>
                                                            </td>
                                                            <td className="py-2 pr-4 text-right font-medium">
                                                                {u.available_tokens ?? u.total_tokens ?? '—'}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {/* ===== FEEDBACK QUEUE TAB ===== */}
                    {activeTab === 'feedback' && (
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <MessageSquare className="w-5 h-5" /> Question Feedback
                                    </CardTitle>
                                    <Button variant="outline" size="sm" onClick={fetchFeedback} disabled={feedbackLoading}>
                                        {feedbackLoading ? 'Loading...' : 'Refresh'}
                                    </Button>
                                </div>
                                <CardDescription>Review flagged questions. Resolving rewards the user with 2 tokens.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {feedbackLoading ? (
                                    <p className="text-sm text-muted-foreground animate-pulse text-center py-4">Loading feedback...</p>
                                ) : feedbackList.length === 0 ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No feedback submissions yet</p>
                                ) : (
                                    <div className="space-y-3">
                                        {feedbackList.map((f: any) => (
                                            <div key={f.id} className={`p-4 rounded-lg border ${f.is_resolved ? 'opacity-60' : ''}`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <Badge variant="outline" className="text-[10px]">{f.category}</Badge>
                                                            <span className="text-xs text-muted-foreground">Q#{f.question}</span>
                                                            {f.is_resolved && (
                                                                <Badge className="text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
                                                                    <CheckCircle className="w-3 h-3 mr-0.5" /> Resolved
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        <p className="text-sm">{f.comment}</p>
                                                        <p className="text-xs text-muted-foreground mt-1">{new Date(f.created_at).toLocaleString()}</p>
                                                    </div>
                                                    {!f.is_resolved && (
                                                        <Button size="sm" variant="outline" onClick={() => handleResolveFeedback(f.id)}>
                                                            <CheckCircle className="w-4 h-4 mr-1" /> Resolve
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </main>
            </div>
        </div>
    );
}
